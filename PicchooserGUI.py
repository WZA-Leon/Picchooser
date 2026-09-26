# -*- coding: utf-8 -*-
"""Picchooser 精细筛片 GUI。

在分类结果目录（dest_folder 或源目录）下，把各分类子文件夹（连拍1、连拍2、
孤立照片、无拍摄信息 …）作为左侧分组列表，右侧大图 + 缩略图条浏览，
人工挑选「成片」：

- 左侧列表区（占 1/5）：显示各分组，左右方向键切换分组。
- 右侧看片区（占 4/5）：
    * 上方：当前图片的大图预览。
    * 下方：当前分组内其它图片的缩略图条。
- 交互：
    * 回车：把当前图片复制到「成片」文件夹并标绿；再次回车取消（删除副本）。
    * 滚轮 / 上下方向键：切换当前图片。

缩略图通过 C++ DLL（thumbnail/thumbnail.dll）调用 Windows Shell 的
IShellItemImageFactory 接口获取；DLL 缺失时自动回退到 Pillow 缩放。

运行：
    uv run python PicchooserGUI.py
"""

import ctypes
import json
import os
import shutil
import sys
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

CONFIG_FILE = "photo_config.json"
DLL_NAME = "thumbnail.dll"
DLL_SUBDIR = "thumbnail"          # DLL 相对本脚本的存放子目录
DONE_FOLDER_NAME = "成片"          # 成片输出文件夹名

# 界面配色
COLOR_BG = "#1e1e1e"
COLOR_PANEL = "#252526"
COLOR_LIST_BG = "#2d2d30"
COLOR_LIST_SEL = "#094771"
COLOR_TEXT = "#d4d4d4"
COLOR_TEXT_DIM = "#808080"
COLOR_DONE = "#4caf50"            # 已选成片的绿色
COLOR_THUMB_BG = "#333333"
COLOR_THUMB_SEL = "#007acc"

# 缩略图条尺寸
THUMB_SIZE = 96                   # 缩略图边长（像素）
THUMB_PAD = 6

# 支持的图片扩展名（读取配置，失败时用默认）
DEFAULT_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff",
                ".webp", ".JPG", ".JPEG", ".PNG", ".BMP")


# ---------------------------------------------------------------------------
# 缩略图 DLL 封装
# ---------------------------------------------------------------------------

class ThumbnailProvider:
    """封装 thumbnail.dll，提供 get(path, size) -> PIL.Image 或 None。"""

    def __init__(self):
        self._dll = None
        self._com_ready = False
        self._init_com()
        self._load_dll()

    def _init_com(self):
        """初始化 COM（STA）。IShellItemImageFactory 依赖 COM。"""
        try:
            # COINIT_APARTMENTTHREADED = 0x2
            hr = ctypes.windll.ole32.CoInitializeEx(None, 0x2)
            # S_OK(0) / S_FALSE(1) 成功；RPC_E_CHANGED_MODE 表示已初始化
            self._com_ready = hr in (0, 1) or hr == -2147417850
        except Exception:
            self._com_ready = False

    def _load_dll(self):
        """按若干候选路径尝试加载 DLL。"""
        base = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base, DLL_SUBDIR, DLL_NAME),
            os.path.join(base, DLL_NAME),
        ]
        # 打包后（_MEIPASS）也尝试一下
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, DLL_NAME))

        for path in candidates:
            if not os.path.exists(path):
                continue
            try:
                dll = ctypes.CDLL(path)
                dll.thumb_get.restype = ctypes.c_int
                dll.thumb_get.argtypes = [
                    ctypes.c_wchar_p,
                    ctypes.c_int,
                    ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
                    ctypes.POINTER(ctypes.c_int),
                    ctypes.POINTER(ctypes.c_int),
                ]
                dll.thumb_free.restype = None
                dll.thumb_free.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
                self._dll = dll
                return
            except OSError:
                continue
        self._dll = None

    @property
    def available(self):
        return self._dll is not None

    def get(self, path, size):
        """获取缩略图，返回 PIL.Image（RGB）或 None。"""
        if self._dll is None:
            return None
        pixels = ctypes.POINTER(ctypes.c_ubyte)()
        w = ctypes.c_int(0)
        h = ctypes.c_int(0)
        rc = self._dll.thumb_get(path, int(size), ctypes.byref(pixels),
                                 ctypes.byref(w), ctypes.byref(h))
        if rc != 0 or not pixels:
            return None
        try:
            width, height = w.value, h.value
            if width <= 0 or height <= 0:
                return None
            # BGRA -> RGB
            buf = ctypes.string_at(pixels, width * height * 4)
            img = Image.frombuffer("RGBA", (width, height), buf, "raw",
                                   "BGRA", 0, 1)
            return img.convert("RGB")
        finally:
            self._dll.thumb_free(pixels)


# ---------------------------------------------------------------------------
# 主界面
# ---------------------------------------------------------------------------

class PicchooserGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Picchooser 精细筛片")
        self.root.configure(bg=COLOR_BG)
        self.root.geometry("1200x760")
        self.root.minsize(900, 600)

        self.config = self._load_config()
        self.exts = tuple(self.config.get("supported_ext") or DEFAULT_EXTS)
        self.result_dir = self._resolve_result_dir()
        self.done_dir = os.path.join(self.result_dir, DONE_FOLDER_NAME)

        self.thumbs = ThumbnailProvider()

        # 数据模型
        self.groups = []          # [(group_name, [file_path, ...]), ...]
        self.group_index = 0      # 当前分组
        self.photo_index = 0      # 当前分组内的图片索引
        self.done_set = set()     # 已选成片的绝对路径集合

        # 图像缓存（避免被 GC）
        self._main_photo = None
        self._thumb_photos = []
        self._thumb_widgets = []

        self._build_ui()
        self._load_groups()
        self._bind_keys()
        self._refresh_all()

    # ---------------- 配置与目录 ----------------

    def _load_config(self):
        base = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, CONFIG_FILE)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _resolve_result_dir(self):
        """分类结果目录：dest_folder 优先，否则源目录。"""
        base = os.path.dirname(os.path.abspath(__file__))
        dest = self.config.get("dest_folder")
        if dest:
            return os.path.abspath(dest)
        src = self.config.get("source_folder") or "."
        if src in (".", ""):
            return base
        return os.path.abspath(src)

    # ---------------- 界面构建 ----------------

    def _build_ui(self):
        # 顶部状态栏
        self.status = tk.Label(
            self.root, text="", anchor="w", bg=COLOR_PANEL, fg=COLOR_TEXT,
            padx=10, pady=6, font=("Microsoft YaHei UI", 10))
        self.status.pack(side="top", fill="x")

        # 主体：左列表 + 右看片
        body = tk.Frame(self.root, bg=COLOR_BG)
        body.pack(side="top", fill="both", expand=True)

        # 左侧列表区（1/5）
        left = tk.Frame(body, bg=COLOR_PANEL, width=240)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        tk.Label(left, text="分组", anchor="w", bg=COLOR_PANEL,
                 fg=COLOR_TEXT_DIM, padx=10, pady=6,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(fill="x")

        self.group_list = tk.Listbox(
            left, bg=COLOR_LIST_BG, fg=COLOR_TEXT, selectbackground=COLOR_LIST_SEL,
            selectforeground="#ffffff", activestyle="none", borderwidth=0,
            highlightthickness=0, font=("Microsoft YaHei UI", 11),
            exportselection=False)
        self.group_list.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.group_list.bind("<<ListboxSelect>>", self._on_group_click)

        # 右侧看片区（4/5）
        right = tk.Frame(body, bg=COLOR_BG)
        right.pack(side="left", fill="both", expand=True)

        # 上方大图
        self.main_canvas = tk.Canvas(right, bg="#111111", highlightthickness=0)
        self.main_canvas.pack(side="top", fill="both", expand=True)
        self.main_canvas.bind("<Configure>", lambda e: self._render_main())

        # 下方缩略图条
        self.thumb_bar = tk.Frame(right, bg=COLOR_THUMB_BG, height=THUMB_SIZE + 2 * THUMB_PAD)
        self.thumb_bar.pack(side="bottom", fill="x")
        self.thumb_bar.pack_propagate(False)

        self.thumb_canvas = tk.Canvas(self.thumb_bar, bg=COLOR_THUMB_BG,
                                      highlightthickness=0, height=THUMB_SIZE + 2 * THUMB_PAD)
        self.thumb_canvas.pack(side="left", fill="both", expand=True)
        self.thumb_scroll = tk.Scrollbar(self.thumb_bar, orient="horizontal",
                                         command=self.thumb_canvas.xview)
        self.thumb_scroll.pack(side="bottom", fill="x")
        self.thumb_canvas.configure(xscrollcommand=self.thumb_scroll.set)

        # 底部提示
        hint = ("← → 切换分组    ↑ ↓ / 滚轮 切换图片    "
                "回车 选为成片 / 取消    成片目录：" + DONE_FOLDER_NAME)
        tk.Label(self.root, text=hint, anchor="w", bg=COLOR_PANEL,
                 fg=COLOR_TEXT_DIM, padx=10, pady=4,
                 font=("Microsoft YaHei UI", 9)).pack(side="bottom", fill="x")

    def _bind_keys(self):
        self.root.bind("<Left>", lambda e: self._switch_group(-1))
        self.root.bind("<Right>", lambda e: self._switch_group(1))
        self.root.bind("<Up>", lambda e: self._switch_photo(-1))
        self.root.bind("<Down>", lambda e: self._switch_photo(1))
        self.root.bind("<Return>", lambda e: self._toggle_done())
        self.root.bind("<KP_Enter>", lambda e: self._toggle_done())
        # 滚轮切换图片
        self.root.bind("<MouseWheel>", self._on_wheel)
        self.main_canvas.bind("<MouseWheel>", self._on_wheel)
        self.thumb_canvas.bind("<MouseWheel>", self._on_wheel)

    # ---------------- 数据加载 ----------------

    def _load_groups(self):
        """扫描分类结果目录下的子文件夹作为分组。"""
        self.groups = []
        if not os.path.isdir(self.result_dir):
            return
        try:
            entries = sorted(os.listdir(self.result_dir))
        except OSError:
            return

        for name in entries:
            full = os.path.join(self.result_dir, name)
            if not os.path.isdir(full):
                continue
            if name == DONE_FOLDER_NAME:
                continue
            files = self._list_images(full)
            if files:
                self.groups.append((name, files))

        # 扫描成片目录，标记已选
        self.done_set = set()
        if os.path.isdir(self.done_dir):
            for name in os.listdir(self.done_dir):
                self.done_set.add(os.path.join(self.done_dir, name))

    def _list_images(self, folder):
        files = []
        try:
            for name in sorted(os.listdir(folder)):
                if name.lower().endswith(tuple(e.lower() for e in self.exts)):
                    files.append(os.path.join(folder, name))
        except OSError:
            pass
        return files

    # ---------------- 渲染 ----------------

    def _refresh_all(self):
        self._refresh_group_list()
        self._refresh_status()
        self._render_main()
        self._render_thumb_bar()

    def _refresh_group_list(self):
        self.group_list.delete(0, tk.END)
        for name, files in self.groups:
            self.group_list.insert(tk.END, f"{name}  ({len(files)})")
        if self.groups:
            self.group_list.selection_clear(0, tk.END)
            self.group_list.selection_set(self.group_index)
            self.group_list.activate(self.group_index)

    def _refresh_status(self):
        if not self.groups:
            self.status.config(text=f"未在 {self.result_dir} 找到可筛选的分组")
            return
        name, files = self.groups[self.group_index]
        cur = files[self.photo_index] if files else ""
        done_mark = "  [已成片]" if cur in self.done_set else ""
        self.status.config(
            text=f"分组：{name}    图片 {self.photo_index + 1}/{len(files)}    "
                 f"{os.path.basename(cur)}{done_mark}")

    def _current_photo(self):
        if not self.groups:
            return None
        _, files = self.groups[self.group_index]
        if not files:
            return None
        return files[self.photo_index]

    def _render_main(self):
        """渲染上方大图。"""
        self.main_canvas.delete("all")
        self._main_photo = None
        path = self._current_photo()
        if not path:
            self.main_canvas.create_text(
                self.main_canvas.winfo_width() // 2,
                self.main_canvas.winfo_height() // 2,
                text="没有可显示的图片", fill=COLOR_TEXT_DIM,
                font=("Microsoft YaHei UI", 14))
            return

        cw = max(self.main_canvas.winfo_width(), 1)
        ch = max(self.main_canvas.winfo_height(), 1)

        # 优先用 DLL 缩略图（大尺寸），失败回退 Pillow
        img = None
        if self.thumbs.available:
            img = self.thumbs.get(path, max(cw, ch))
        if img is None:
            img = self._load_with_pillow(path)
        if img is None:
            self.main_canvas.create_text(
                cw // 2, ch // 2, text="无法加载图片", fill=COLOR_TEXT_DIM,
                font=("Microsoft YaHei UI", 14))
            return

        # 等比缩放到画布内
        img = self._fit(img, cw - 20, ch - 20)
        self._main_photo = ImageTk.PhotoImage(img)
        self.main_canvas.create_image(cw // 2, ch // 2, image=self._main_photo)

        # 已成片：绿色边框
        if path in self.done_set:
            self.main_canvas.create_rectangle(
                4, 4, cw - 4, ch - 4, outline=COLOR_DONE, width=4)

    def _render_thumb_bar(self):
        """渲染下方缩略图条。"""
        self.thumb_canvas.delete("all")
        self._thumb_photos = []
        self._thumb_widgets = []
        if not self.groups:
            return
        _, files = self.groups[self.group_index]

        x = THUMB_PAD
        for idx, path in enumerate(files):
            img = None
            if self.thumbs.available:
                img = self.thumbs.get(path, THUMB_SIZE)
            if img is None:
                img = self._load_with_pillow(path)
            if img is None:
                img = Image.new("RGB", (THUMB_SIZE, THUMB_SIZE), (60, 60, 60))
            img = self._fit(img, THUMB_SIZE, THUMB_SIZE)
            photo = ImageTk.PhotoImage(img)
            self._thumb_photos.append(photo)

            y = THUMB_PAD
            item = self.thumb_canvas.create_image(x, y, anchor="nw", image=photo)
            self._thumb_widgets.append((item, idx))

            # 选中 / 已成片 边框
            if idx == self.photo_index:
                outline, width = COLOR_THUMB_SEL, 3
            elif path in self.done_set:
                outline, width = COLOR_DONE, 3
            else:
                outline, width = "#555555", 1
            self.thumb_canvas.create_rectangle(
                x, y, x + THUMB_SIZE, y + THUMB_SIZE,
                outline=outline, width=width)

            x += THUMB_SIZE + THUMB_PAD

        self.thumb_canvas.configure(scrollregion=(0, 0, x, THUMB_SIZE + 2 * THUMB_PAD))
        self._scroll_thumb_to_current()

    def _scroll_thumb_to_current(self):
        """让缩略图条滚动到当前图片可见。"""
        if not self.groups:
            return
        _, files = self.groups[self.group_index]
        total = len(files)
        if total == 0:
            return
        content_w = total * (THUMB_SIZE + THUMB_PAD) + THUMB_PAD
        view_w = self.thumb_canvas.winfo_width()
        if content_w <= view_w:
            self.thumb_canvas.xview_moveto(0)
            return
        target = self.photo_index * (THUMB_SIZE + THUMB_PAD)
        # 居中显示
        frac = (target - (view_w - THUMB_SIZE) / 2) / content_w
        frac = max(0.0, min(1.0, frac))
        self.thumb_canvas.xview_moveto(frac)

    # ---------------- 图像工具 ----------------

    @staticmethod
    def _load_with_pillow(path):
        try:
            return Image.open(path).convert("RGB")
        except Exception:
            return None

    @staticmethod
    def _fit(img, max_w, max_h):
        """等比缩放到不超过 max_w x max_h。"""
        max_w = max(int(max_w), 1)
        max_h = max(int(max_h), 1)
        w, h = img.size
        if w <= 0 or h <= 0:
            return img
        scale = min(max_w / w, max_h / h)
        # 小图不放大
        if scale >= 1.0:
            return img
        return img.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                          Image.LANCZOS)

    # ---------------- 交互 ----------------

    def _on_group_click(self, event):
        sel = self.group_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx != self.group_index:
            self.group_index = idx
            self.photo_index = 0
            self._refresh_all()

    def _switch_group(self, delta):
        if not self.groups:
            return
        new = self.group_index + delta
        if 0 <= new < len(self.groups):
            self.group_index = new
            self.photo_index = 0
            self._refresh_all()

    def _switch_photo(self, delta):
        if not self.groups:
            return
        _, files = self.groups[self.group_index]
        if not files:
            return
        new = self.photo_index + delta
        if 0 <= new < len(files):
            self.photo_index = new
            self._refresh_status()
            self._render_main()
            self._render_thumb_bar()

    def _on_wheel(self, event):
        # Windows: event.delta 正=上滚，负=下滚
        self._switch_photo(-1 if event.delta > 0 else 1)

    def _toggle_done(self):
        """回车：选为成片（复制并标绿）或取消（删除副本）。"""
        path = self._current_photo()
        if not path:
            return
        if path in self.done_set:
            self._cancel_done(path)
        else:
            self._mark_done(path)
        self._refresh_status()
        self._render_main()
        self._render_thumb_bar()

    def _mark_done(self, path):
        try:
            os.makedirs(self.done_dir, exist_ok=True)
            target = os.path.join(self.done_dir, os.path.basename(path))
            # 同名冲突时加序号
            if os.path.exists(target) and os.path.abspath(target) != os.path.abspath(path):
                stem, ext = os.path.splitext(os.path.basename(path))
                i = 1
                while os.path.exists(target):
                    target = os.path.join(self.done_dir, f"{stem}_{i}{ext}")
                    i += 1
            shutil.copy2(path, target)
            self.done_set.add(path)
        except OSError as e:
            messagebox.showerror("复制失败", f"无法复制到成片目录：\n{e}")

    def _cancel_done(self, path):
        target = os.path.join(self.done_dir, os.path.basename(path))
        try:
            if os.path.exists(target):
                os.remove(target)
        except OSError as e:
            messagebox.showerror("取消失败", f"无法删除成片副本：\n{e}")
            return
        self.done_set.discard(path)


def run_gui():
    """启动图形界面（阻塞直到窗口关闭）。供 Picchooser.py 菜单调用。"""
    root = tk.Tk()
    app = PicchooserGUI(root)
    if not app.thumbs.available:
        # 提示 DLL 未加载，但程序仍可用 Pillow 回退
        app.status.config(
            text=app.status.cget("text") +
                 "    [提示] 未找到 thumbnail.dll，已回退 Pillow 缩放")
    root.mainloop()


def main():
    run_gui()


if __name__ == "__main__":
    main()
