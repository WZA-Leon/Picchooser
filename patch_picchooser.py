# -*- coding: utf-8 -*-
"""一次性补丁脚本：为 Picchooser.py 主菜单添加 [7] 清理缓存 选项。"""
import io

PATH = "Picchooser.py"
with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

orig = src

# 1) ask_mode 签名：新增 on_clear_cache 参数
old_sig = (
    "def ask_mode(default_copy=True, prompt=input, on_edit=None,\n"
    "             source_dir=None, supported_ext=(), on_change_dir=None,\n"
    "             on_tutorial=None, on_gui=None):"
)
new_sig = (
    "def ask_mode(default_copy=True, prompt=input, on_edit=None,\n"
    "             source_dir=None, supported_ext=(), on_change_dir=None,\n"
    "             on_tutorial=None, on_gui=None, on_clear_cache=None):"
)
assert old_sig in src, "签名未找到"
src = src.replace(old_sig, new_sig, 1)

# 2) ask_mode docstring：补充 on_clear_cache 说明
old_doc = (
    "    :param on_gui: 选择 [6] 精细筛片（GUI）时调用的回调，返回后重新询问；为 None 时不显示该选项\n"
    "    :return: True=复制原图；False=移动原图；None=用户选择退出"
)
new_doc = (
    "    :param on_gui: 选择 [6] 精细筛片（GUI）时调用的回调，返回后重新询问；为 None 时不显示该选项\n"
    "    :param on_clear_cache: 选择 [7] 清理缓存时调用的回调，返回后重新询问；为 None 时不显示该选项\n"
    "    :return: True=复制原图；False=移动原图；None=用户选择退出"
)
assert old_doc in src, "docstring 未找到"
src = src.replace(old_doc, new_doc, 1)

# 3) 菜单项：在 [6] 之后、[0] 之前插入 [7]
old_menu = (
    "        if on_gui is not None:\n"
    "            menu += colorize(\"  [6] 精细筛片（图形界面）\", \"white\") + \"\\n\"\n"
    "            valid_choices.append(\"6\")\n"
    "        menu += colorize(\"  [0] 退出\", \"white\") + \"\\n\""
)
new_menu = (
    "        if on_gui is not None:\n"
    "            menu += colorize(\"  [6] 精细筛片（图形界面）\", \"white\") + \"\\n\"\n"
    "            valid_choices.append(\"6\")\n"
    "        if on_clear_cache is not None:\n"
    "            menu += colorize(\"  [7] 清理缓存\", \"white\") + \"\\n\"\n"
    "            valid_choices.append(\"7\")\n"
    "        menu += colorize(\"  [0] 退出\", \"white\") + \"\\n\""
)
assert old_menu in src, "菜单项未找到"
src = src.replace(old_menu, new_menu, 1)

# 4) 输入分发：在 [6] 分支之后添加 [7] 分支
old_dispatch = (
    "        if answer == \"6\" and on_gui is not None:\n"
    "            on_gui()\n"
    "            continue\n"
    "        log(f\"输入无效，请输入 {tail.replace('请输入 ', '')}，或直接回车使用默认值。\")"
)
new_dispatch = (
    "        if answer == \"6\" and on_gui is not None:\n"
    "            on_gui()\n"
    "            continue\n"
    "        if answer == \"7\" and on_clear_cache is not None:\n"
    "            on_clear_cache()\n"
    "            continue\n"
    "        log(f\"输入无效，请输入 {tail.replace('请输入 ', '')}，或直接回车使用默认值。\")"
)
assert old_dispatch in src, "分发分支未找到"
src = src.replace(old_dispatch, new_dispatch, 1)

assert src != orig, "没有任何改动"
with io.open(PATH, "w", encoding="utf-8", newline="") as f:
    f.write(src)
print("ask_mode 补丁完成")
