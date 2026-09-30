# -*- coding: utf-8 -*-
"""补丁 2：新增 get_result_dir / clear_cache 函数，并在 main 中接入 [7] 清理缓存。"""
import io

PATH = "Picchooser.py"
with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

orig = src

# 1) 在 get_supported_files 之前插入 get_result_dir 与 clear_cache
anchor = "def get_supported_files(dir_path, supported_ext):"
assert anchor in src, "锚点未找到"

new_funcs = '''def get_result_dir(config):
    """
    解析分类结果目录（与 PicchooserGUI._resolve_result_dir 保持一致）：
    优先使用配置里的 dest_folder，否则回退到源目录。
    :param config: 配置字典
    :return: 结果目录绝对路径
    """
    dest = config.get("dest_folder")
    if dest:
        return os.path.abspath(dest)
    return get_source_dir(config)


def clear_cache(config, prompt=input):
    """
    「清理缓存」：删除结果目录下的 temp 缩略图缓存文件夹（PicchooserGUI 生成）。
    仅删除 temp 目录本身，不影响分类结果与成片。
    :param config: 配置字典
    :param prompt: 读取用户输入的函数（默认 input，便于测试注入）
    """
    clear_screen()

    result_dir = get_result_dir(config)
    temp_dir = os.path.join(result_dir, TEMP_DIR_NAME)

    log_colored("清理缓存", "cyan")
    log(f"  缓存目录：{temp_dir}")

    if not os.path.isdir(temp_dir):
        log_colored("[提示] 未发现缓存目录，无需清理。", "yellow")
        wait_for_enter(prompt)
        clear_screen()
        return

    # 统计缓存文件数量与占用空间，便于用户确认
    file_count = 0
    total_size = 0
    try:
        for name in os.listdir(temp_dir):
            full = os.path.join(temp_dir, name)
            if os.path.isfile(full):
                file_count += 1
                try:
                    total_size += os.path.getsize(full)
                except OSError:
                    pass
    except OSError as e:
        log_colored(f"[错误] 无法读取缓存目录：{describe_error(e)}", "red")
        wait_for_enter(prompt)
        clear_screen()
        return

    size_mb = total_size / (1024 * 1024)
    log(f"  共 {file_count} 个缓存文件，约 {size_mb:.2f} MB")

    # 二次确认，避免误删
    try:
        answer = prompt("确认清理以上缓存？(y/N)：").strip().lower()
    except EOFError:
        answer = "n"
    if answer not in ("y", "yes"):
        log_colored("[提示] 已取消清理。", "yellow")
        wait_for_enter(prompt)
        clear_screen()
        return

    # 删除 temp 目录（含其中所有文件）
    try:
        shutil.rmtree(temp_dir)
        log_colored(f"[完成] 已清理缓存，释放约 {size_mb:.2f} MB。", "green")
    except OSError as e:
        log_colored(f"[错误] 清理缓存失败：{describe_error(e)}", "red")

    wait_for_enter(prompt)
    clear_screen()


'''
src = src.replace(anchor, new_funcs + anchor, 1)

# 2) main 中新增 on_clear_cache 回调（放在 on_gui 定义之后）
old_gui_tail = (
    "            try:\n"
    "                PicchooserGUI.run_gui()\n"
    "            except Exception as e:\n"
    "                log_colored(f\"[错误] 图形界面运行出错：{describe_error(e)}\", \"red\")\n"
    "                wait_for_enter(prompt)\n"
)
new_gui_tail = old_gui_tail + (
    "\n"
    "        def on_clear_cache():\n"
    "            \"\"\"选择 [7] 清理缓存：删除结果目录下的 temp 缩略图缓存\"\"\"\n"
    "            clear_cache(config, prompt)\n"
)
assert old_gui_tail in src, "on_gui 尾部未找到"
src = src.replace(old_gui_tail, new_gui_tail, 1)

# 3) 调用 ask_mode 时传入 on_clear_cache
old_call = (
    "                on_tutorial=on_tutorial,\n"
    "                on_gui=on_gui,\n"
    "            )"
)
new_call = (
    "                on_tutorial=on_tutorial,\n"
    "                on_gui=on_gui,\n"
    "                on_clear_cache=on_clear_cache,\n"
    "            )"
)
assert old_call in src, "ask_mode 调用未找到"
src = src.replace(old_call, new_call, 1)

assert src != orig, "没有任何改动"
with io.open(PATH, "w", encoding="utf-8", newline="") as f:
    f.write(src)
print("补丁 2 完成")
