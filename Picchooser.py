import os
import sys
import json
import errno
import exifread
import datetime
import shutil


def get_app_dir():
    """
    获取程序所在目录
    兼容 PyInstaller 打包后的 exe（打包后 __file__ 不可靠，用 sys.executable）
    """
    if getattr(sys, 'frozen', False):
        # 打包后：exe 所在目录
        return os.path.dirname(sys.executable)
    # 源码运行：脚本所在目录
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(filename):
    """
    获取随程序分发的资源文件（如教程 txt）的完整路径
    打包为单文件 exe 时，资源会被解包到 sys._MEIPASS 临时目录；
    源码运行时直接取脚本所在目录。
    :param filename: 资源文件名，如 "tutorial.txt"
    :return: 资源文件完整路径
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller onefile：优先用解包目录
        base_dir = getattr(sys, '_MEIPASS', get_app_dir())
    else:
        base_dir = get_app_dir()
    return os.path.join(base_dir, filename)


# ===================== 配置文件 =====================
# JSON配置文件路径：优先运行命令的当前目录，其次程序所在目录
def _find_config():
    cwd_cfg = os.path.join(os.getcwd(), "photo_config.json")
    if os.path.isfile(cwd_cfg):
        return cwd_cfg
    return os.path.join(get_app_dir(), "photo_config.json")


CONFIG_FILE = _find_config()

# 参数默认值：当 JSON 里缺少某项时，用这里的值兜底
DEFAULT_CONFIG = {
    "source_folder": ".",  # 源图片文件夹；"." 或 null = 运行命令的当前目录
    "dest_folder": None,                      # None = 源目录下生成「分类结果」
    "copy_mode": True,                        # True=复制原图（保留原图）；False=移动原图
    "burst_threshold": 1.0,                   # 连拍时间阈值（秒）
    "supported_ext": [".jpg", ".jpeg", ".JPG", ".JPEG"],  # 支持的图片格式
    "burst_folder_prefix": "连拍",            # 连拍文件夹前缀
    "single_folder_name": "孤立照片",          # 单张照片文件夹
    "no_exif_folder_name": "无拍摄信息",       # 读不到EXIF的文件夹
}

def log(message):
    """输出到控制台（命令行调用，立即刷新）；按前缀自动着色"""
    print(auto_colorize(message), flush=True)


# ===================== 控制台颜色高亮 =====================
# ANSI 转义序列；当控制台不支持或输出被重定向时自动降级为纯文本
ANSI_RESET = "\033[0m"
ANSI_COLORS = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bold": "\033[1m",
    # 橙色：用 256 色模式的 208 号色，兼容主流现代终端
    "orange": "\033[38;5;208m",
}
# 是否启用颜色：默认关闭，由 enable_ansi() 打开
_COLOR_ENABLED = False


def enable_ansi():
    """
    尝试启用控制台 ANSI 颜色支持（Windows 10+），失败则保持纯文本
    :return: 启用成功返回 True
    """
    global _COLOR_ENABLED

    # 输出被重定向到文件/管道时不着色，避免留下转义字符
    if not sys.stdout.isatty():
        _COLOR_ENABLED = False
        return False

    # 非 Windows（POSIX）终端默认支持 ANSI
    if os.name != "nt":
        _COLOR_ENABLED = True
        return True

    try:
        # 打开 Windows 控制台的虚拟终端处理（ENABLE_VIRTUAL_TERMINAL_PROCESSING）
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            _COLOR_ENABLED = False
            return False
        # 0x0004 = ENABLE_VIRTUAL_TERMINAL_PROCESSING
        if not kernel32.SetConsoleMode(handle, mode.value | 0x0004):
            _COLOR_ENABLED = False
            return False
        _COLOR_ENABLED = True
        return True
    except Exception:
        _COLOR_ENABLED = False
        return False


def colorize(text, color):
    """
    给文本套上颜色（未启用颜色时原样返回）
    :param text: 原始文本
    :param color: ANSI_COLORS 中的颜色名
    :return: 着色后的文本
    """
    if not _COLOR_ENABLED:
        return text
    code = ANSI_COLORS.get(color, "")
    if not code:
        return text
    return f"{code}{text}{ANSI_RESET}"


def log_colored(message, color):
    """输出带颜色的控制台信息"""
    log(colorize(message, color))


def auto_colorize(message):
    """
    根据消息前缀自动推断颜色，让普通 log() 调用也能高亮
    :param message: 消息文本
    :return: 着色后的文本
    """
    if not _COLOR_ENABLED:
        return message
    stripped = message.lstrip()
    if stripped.startswith("[错误]"):
        return colorize(message, "red")
    if stripped.startswith("[完成]"):
        return colorize(message, "green")
    if stripped.startswith("[警告]"):
        return colorize(message, "red")
    if stripped.startswith("[提示]"):
        return colorize(message, "cyan")
    return message


def is_disk_full_error(error):
    """
    判断异常是不是「磁盘空间不足」（兼容 Windows 与 POSIX）
    :param error: 捕获到的异常对象
    :return: 是磁盘满返回 True，否则 False
    """
    if getattr(error, "errno", None) == errno.ENOSPC:
        return True
    # Windows: 39=ERROR_HANDLE_DISK_FULL，112=ERROR_DISK_FULL
    if getattr(error, "winerror", None) in (39, 112):
        return True
    return False


def describe_error(error):
    """
    把底层异常翻译成更易懂的中文提示，便于命令行排查问题
    :param error: 捕获到的异常对象
    :return: 提示文本
    """
    if is_disk_full_error(error):
        return f"磁盘空间不足，请清理磁盘后重试（{error}）"
    if isinstance(error, PermissionError):
        return f"没有访问权限，请检查文件/文件夹权限（{error}）"
    if isinstance(error, FileNotFoundError):
        return f"找不到文件或目录（{error}）"
    return str(error)


def load_config(config_path=CONFIG_FILE):
    """
    从 JSON 文件读取配置，缺失项用默认值补齐
    :param config_path: JSON配置文件路径
    :return: 配置字典
    """
    config = dict(DEFAULT_CONFIG)
    if not os.path.isfile(config_path):
        log(f"[警告] 未找到配置文件 {config_path}，将使用默认参数")
        return config
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
        config.update(user_config)
        log(f"已加载配置文件：{config_path}")
        return config
    except Exception as e:
        log(f"[警告] 读取配置文件失败: {e}，将使用默认参数")
        return config


def save_config(config, config_path=CONFIG_FILE):
    """
    把配置写回 JSON 文件（UTF-8、缩进、保留中文）
    :param config: 配置字典
    :param config_path: JSON配置文件路径
    :raises OSError: 写入失败
    """
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# 「修改配置」菜单里可编辑的字段（顺序即菜单顺序）
EDITABLE_FIELDS = (
    "source_folder",
    "dest_folder",
    "copy_mode",
    "burst_threshold",
    "supported_ext",
    "burst_folder_prefix",
    "single_folder_name",
    "no_exif_folder_name",
)


def parse_config_value(field, raw):
    """
    把用户在菜单里输入的字符串，按字段类型转换成正确的值
    :param field: 字段名
    :param raw: 用户输入的原始字符串
    :return: 转换后的值
    :raises ValueError: 输入不合法
    """
    text = raw.strip()
    if field == "copy_mode":
        if text.lower() in ("true", "1", "yes", "y", "是", "复制"):
            return True
        if text.lower() in ("false", "0", "no", "n", "否", "移动"):
            return False
        raise ValueError("copy_mode 只能填 true 或 false")
    if field == "burst_threshold":
        try:
            return float(text)
        except ValueError:
            raise ValueError("burst_threshold 必须是数字（如 1 或 3.5）")
    if field == "dest_folder":
        if text == "" or text.lower() == "null":
            return None
    if field == "supported_ext":
        items = [part.strip() for part in text.replace(";", ",").split(",")]
        items = [item for item in items if item]
        if not items:
            raise ValueError("supported_ext 至少要有一个扩展名（如 .jpg,.png）")
        return items
    # 其余字段按字符串处理
    return raw if field != "dest_folder" else text


def edit_config(config, config_path=CONFIG_FILE, prompt=input):
    """
    交互式修改配置：列出字段和当前值，选择序号修改并写回文件
    :param config: 当前配置字典（会被就地更新）
    :param config_path: JSON配置文件路径
    :param prompt: 读取用户输入的函数（默认 input，便于测试注入）
    :return: 修改后的配置字典
    """
    # 记录上一次的保存/错误提示，清屏后补打，避免提示被清掉看不到
    last_notice = None

    while True:
        # 每次显示菜单前清屏，避免历史输出堆叠
        clear_screen()
        if last_notice:
            log(last_notice)
            log("")
            last_notice = None
        log_colored("===== 修改配置 =====", "cyan")
        for i, field in enumerate(EDITABLE_FIELDS, start=1):
            value = config.get(field)
            if isinstance(value, list):
                value = "、".join(str(x) for x in value)
            elif value is None:
                value = "（默认）"
            log_colored(f"  [{i}] {field} = {value}", "white")
        log_colored("  [0] 返回", "white")

        try:
            choice = prompt("请输入要修改的序号（0 返回）：").strip()
        except EOFError:
            log("[提示] 未检测到交互输入，跳过修改配置")
            return config

        if choice == "0" or choice == "":
            # 返回主菜单前清屏，避免残留的配置菜单挡在主菜单前面
            clear_screen()
            return config
        if not choice.isdigit() or not (1 <= int(choice) <= len(EDITABLE_FIELDS)):
            last_notice = "输入无效，请输入列表中的序号。"
            continue

        field = EDITABLE_FIELDS[int(choice) - 1]
        try:
            raw = prompt(f"请输入 {field} 的新值（dest_folder 输入 null 表示默认）：")
        except EOFError:
            log("[提示] 未检测到交互输入，跳过修改配置")
            return config

        try:
            config[field] = parse_config_value(field, raw)
        except ValueError as e:
            last_notice = f"[错误] {e}"
            continue

        try:
            save_config(config, config_path)
        except OSError as e:
            last_notice = f"[错误] 保存配置失败：{describe_error(e)}"
            continue
        last_notice = f"[完成] 已保存：{field} = {config[field]}"


def get_capture_time(img_path):
    """
    读取图片EXIF中的原始拍摄时间
    :param img_path: 图片完整路径
    :return: datetime对象；读取失败返回None
    """
    try:
        with open(img_path, 'rb') as f:
            exif_tags = exifread.process_file(f, details=False)

        if 'EXIF DateTimeOriginal' in exif_tags:
            time_str = str(exif_tags['EXIF DateTimeOriginal'])
            return datetime.datetime.strptime(time_str, '%Y:%m:%d %H:%M:%S')

        return None
    except Exception as e:
        log(f"[警告] 读取文件 {os.path.basename(img_path)} 时间失败: {str(e)}")
        return None


def copy_or_move(source_path, target_path, copy_mode):
    """
    把源文件复制或移动到目标路径
    :param source_path: 源文件完整路径
    :param target_path: 目标文件完整路径
    :param copy_mode: True=复制（保留原图）；False=移动（不保留原图）
    :return: "copy" = 已复制；"move" = 已移动
    :raises OSError: 复制/移动失败
    """
    # 目标已存在时先删除，避免复制时覆盖冲突或移动时 FileExistsError
    if os.path.exists(target_path):
        os.remove(target_path)

    if copy_mode:
        shutil.copy2(source_path, target_path)
        return "copy"
    shutil.move(source_path, target_path)
    return "move"


def classify_photos(config):
    """
    根据拍摄时间自动分类照片
    :param config: 配置字典（由 load_config 得到）
    :return: 结果摘要文本（供弹窗展示）
    """
    # ---------- 从配置中取出各项参数 ----------
    # source_folder 为 "." 或 null 时，表示运行命令的当前工作目录
    source_dir = config["source_folder"]
    if source_dir in (None, "", "."):
        source_dir = os.getcwd()
    else:
        source_dir = os.path.abspath(source_dir)
    dest_dir = config["dest_folder"]
    log(f"源目录：{source_dir}")
    copy_mode = config["copy_mode"]
    burst_threshold = config["burst_threshold"]
    supported_ext = tuple(config["supported_ext"])
    burst_folder_prefix = config["burst_folder_prefix"]
    single_folder_name = config["single_folder_name"]
    no_exif_folder_name = config["no_exif_folder_name"]

    # 初始化目标目录
    if dest_dir is None:
        dest_dir = os.path.join(source_dir, "分类结果")

    # 校验源目录
    if not os.path.isdir(source_dir):
        log(f"[错误] 源目录不存在：{source_dir}")
        return f"源目录不存在：\n{source_dir}"

    # ---------- 第一步：遍历源目录，收集所有图片和拍摄时间 ----------
    photo_with_time = []  # 格式：(拍摄时间, 文件完整路径, 文件名)
    no_exif_files = []    # 读不到EXIF的文件列表
    skipped_files = []    # 被跳过的、格式不支持的普通文件

    try:
        entries = os.listdir(source_dir)
    except OSError as e:
        log(f"[错误] 无法读取源目录：{source_dir}\n       原因：{describe_error(e)}")
        return f"无法读取源目录：\n{source_dir}"

    for filename in entries:
        file_full_path = os.path.join(source_dir, filename)
        if not os.path.isfile(file_full_path):
            continue
        if not filename.endswith(supported_ext):
            skipped_files.append(filename)
            continue

        capture_time = get_capture_time(file_full_path)
        if capture_time is not None:
            photo_with_time.append((capture_time, file_full_path, filename))
        else:
            no_exif_files.append(file_full_path)

        # 一张能用的图片都没有：区分「目录为空」和「格式都不支持」，给出更明确的提示
    if not photo_with_time and not no_exif_files:
        if skipped_files:
            log(f"[错误] 目录里有 {len(skipped_files)} 个文件，但没有一个是支持的图片格式")
            log(f"       当前支持的格式：{'、'.join(config['supported_ext'])}")
            log('       可修改配置 supported_ext 添加格式（例如 ".png"、".heic"）后重试')
        else:
            log(f"[错误] 源目录里没有找到任何文件：{source_dir}")
        return "源目录中未找到支持的图片文件"

    # 有图片被处理，但同时也跳过了格式不支持的文件：提醒一下，避免漏图
    if skipped_files:
        log(f"[提示] 已跳过 {len(skipped_files)} 个格式不支持的文件（支持：{'、'.join(config['supported_ext'])}）")

    # ---------- 第二步：按拍摄时间从早到晚排序 ----------
    photo_with_time.sort(key=lambda item: item[0])

    # ---------- 第三步：按时间间隔分组（连拍组 / 孤立组） ----------
    groups = []
    if photo_with_time:
        current_group = [photo_with_time[0]]
        for i in range(1, len(photo_with_time)):
            prev_time = photo_with_time[i-1][0]
            curr_time = photo_with_time[i][0]
            time_delta = (curr_time - prev_time).total_seconds()

            if time_delta <= burst_threshold:
                current_group.append(photo_with_time[i])
            else:
                groups.append(current_group)
                current_group = [photo_with_time[i]]
        groups.append(current_group)

    # ---------- 第四步：创建文件夹，分发文件 ----------
    try:
        os.makedirs(dest_dir, exist_ok=True)
    except OSError as e:
        log(f"[错误] 无法创建结果文件夹：{dest_dir}\n       原因：{describe_error(e)}")
        raise

    burst_index = 0
    single_folder = os.path.join(dest_dir, single_folder_name)
    no_exif_folder = os.path.join(dest_dir, no_exif_folder_name)

    def dispatch(file_path, target_folder):
        """把文件放入目标文件夹：copy_mode 时复制原图，否则移动原图"""
        target_path = os.path.join(target_folder, os.path.basename(file_path))
        try:
            copy_or_move(file_path, target_path, copy_mode)
        except OSError as e:
            if is_disk_full_error(e):
                log(f"[错误] 磁盘空间不足，处理 {os.path.basename(file_path)} 时写入失败，请清理磁盘后重试")
            raise

    for group in groups:
        if len(group) > 1:
            burst_index += 1
            folder_name = f"{burst_folder_prefix}{burst_index}"
            target_folder = os.path.join(dest_dir, folder_name)
            os.makedirs(target_folder, exist_ok=True)

            for _, file_path, fname in group:
                dispatch(file_path, target_folder)
            log(f"已分类 → {folder_name}（{len(group)} 张）")
        else:
            os.makedirs(single_folder, exist_ok=True)
            _, file_path, fname = group[0]
            dispatch(file_path, single_folder)

    if no_exif_files:
        os.makedirs(no_exif_folder, exist_ok=True)
        for file_path in no_exif_files:
            dispatch(file_path, no_exif_folder)
        log(f"无拍摄信息 → {len(no_exif_files)} 张")

    # ---------- 输出统计结果 ----------
    single_count = sum(1 for g in groups if len(g) == 1)
    if copy_mode:
        mode_line = "处理方式：复制原图\n"
    else:
        mode_line = "处理方式：移动原图\n"
    summary = (
        "分类完成！\n"
        f"共处理 {len(photo_with_time) + len(no_exif_files)} 张图片\n"
        f"连拍组：{burst_index} 组\n"
        f"孤立照片：{single_count} 张\n"
        f"无拍摄信息：{len(no_exif_files)} 张\n"
        + mode_line +
        f"结果保存路径：{dest_dir}"
    )
    log(colorize("\n" + "=" * 40, "white"))
    log_colored("分类完成！", "green")
    log(summary)
    log(colorize("=" * 40, "white"))
    return summary


def get_source_dir(config):
    """
    根据配置解析出真正的源目录绝对路径
    :param config: 配置字典
    :return: 源目录绝对路径
    """
    source_dir = config.get("source_folder")
    if source_dir in (None, "", "."):
        return os.getcwd()
    return os.path.abspath(source_dir)


def get_supported_files(dir_path, supported_ext):
    """
    列出目录下扩展名属于 supported_ext 的文件（只统计文件，不含子目录）
    :param dir_path: 目录路径
    :param supported_ext: 支持的扩展名序列，如 [".jpg", ".png"]
    :return: 匹配到的文件名列表；目录不可读时返回 None
    """
    try:
        entries = os.listdir(dir_path)
    except OSError:
        return None
    exts = tuple(supported_ext)
    return [name for name in entries
            if name.endswith(exts) and os.path.isfile(os.path.join(dir_path, name))]


def has_supported_files(dir_path, supported_ext, max_depth=3):
    """
    递归判断目录内（含子目录）是否存在支持的图片文件，最多向下搜索 max_depth 层
    :param dir_path: 目录路径
    :param supported_ext: 支持的扩展名序列
    :param max_depth: 最大递归层数（3 表示包含自身所在层，向下探 2 层）
    :return: 存在支持的图片返回 True，否则 False
    """
    if get_supported_files(dir_path, supported_ext):
        return True
    if max_depth <= 1:
        return False
    for folder in list_subfolders(dir_path):
        if has_supported_files(folder, supported_ext, max_depth - 1):
            return True
    return False


def clear_screen():
    """清空控制台屏幕（兼容 Windows 与 POSIX）"""
    os.system("cls" if os.name == "nt" else "clear")


def list_subfolders(dir_path):
    """
    列出目录下的子文件夹（按名称排序），用于「选择文件夹」菜单
    :param dir_path: 目录路径
    :return: 子文件夹完整路径列表；不可读时返回空列表
    """
    try:
        entries = os.listdir(dir_path)
    except OSError:
        return []
    folders = [os.path.join(dir_path, name) for name in entries
               if os.path.isdir(os.path.join(dir_path, name))]
    folders.sort(key=lambda p: os.path.basename(p).lower())
    return folders


def list_drives():
    """
    列出可切换的磁盘分区（根目录），用于在磁盘根目录时切换分区
    :return: 分区根路径列表，如 ["C:\\", "D:\\"]；不支持的平台返回空列表
    """
    drives = []
    if os.name == "nt":
        # Windows：遍历所有盘符，挑选真实存在的分区
        import string
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.exists(root):
                drives.append(root)
    else:
        # POSIX：/ 是根，其它挂载点难以可靠枚举，仅返回根目录
        if os.path.exists("/"):
            drives.append("/")
    return drives


def choose_folder(start_dir, supported_ext, prompt=input):
    """
    交互式切换目录：列出当前目录的子文件夹和上级目录，用 1、2、3… 选择
    选中没有支持的图片的目录后，可继续进入下级文件夹或返回上级
    :param start_dir: 起始目录（当前源目录）
    :param supported_ext: 支持的扩展名序列
    :param prompt: 读取用户输入的函数（默认 input，便于测试注入）
    :return: 选中的目录绝对路径；用户取消则返回 None
    """
    current = os.path.abspath(start_dir)

    while True:
        clear_screen()
        # 递归（最多 3 层）判断当前目录及其子目录是否存在支持的图片
        has_supported = has_supported_files(current, supported_ext, max_depth=3)
        no_supported = not has_supported

        log("")
        log_colored("===== 选择文件夹 =====", "cyan")
        # 当前目录用橙色高亮，方便一眼确认所在位置
        log_colored(f"  当前目录：{current}", "orange")
        if no_supported:
            log_colored("  （该目录及其子目录均没有支持的图片）", "yellow")

        # 收集可选目标：返回上级 + 子文件夹 + 当前目录，按序号对应
        options = []  # 按序号存放可选目录的完整路径

        # 上级目录（始终放在第一个位置）；若已是根目录则改为「切换分区」
        parent = os.path.dirname(current)
        if parent and parent != current:
            log_colored(f"    [1] .. （返回上级目录）", "white")
            options.append(parent)
        else:
            # 已是磁盘根目录：列出其它分区供切换
            drives = [d for d in list_drives() if os.path.abspath(d) != current]
            if drives:
                log_colored("  切换分区：", "white")
                for drive in drives:
                    # 分区选项用青色高亮，与子文件夹区分开
                    log_colored(f"    [{len(options) + 1}] {drive}", "cyan")
                    options.append(drive)

        # 子文件夹：含支持图片的用绿色高亮，不含的用白色并加标记
        log_colored("  子文件夹：", "white")
        subfolders = list_subfolders(current)
        if subfolders:
            for folder in subfolders:
                # 递归（最多 3 层）判断该子文件夹内是否有支持的图片
                if has_supported_files(folder, supported_ext, max_depth=2):
                    mark = ""
                    color = "green"
                else:
                    mark = "（无支持图片）"
                    color = "white"
                log_colored(f"    [{len(options) + 1}] {os.path.basename(folder)} {mark}", color)
                options.append(folder)
        else:
            log_colored("    （没有子文件夹）", "white")

        # 使用当前目录
        use_current_index = len(options) + 1
        log_colored(f"    [{use_current_index}] 使用当前目录", "white")
        log_colored("    [0] 取消", "white")

        try:
            choice = prompt("请选择要切换到的文件夹序号（0 取消）：").strip()
        except EOFError:
            log("[提示] 未检测到交互输入，取消切换目录")
            return None

        if choice == "0" or choice == "":
            # 取消切换：清屏后再返回，避免残留的菜单挡在主菜单前面
            clear_screen()
            return None
        if not choice.isdigit():
            log("输入无效，请输入列表中的序号。")
            continue

        num = int(choice)
        if num == use_current_index:
            if no_supported:
                log("[警告] 当前目录及其子目录都没有支持的图片，请选择其它文件夹。")
                continue
            clear_screen()
            return current
        if 1 <= num <= len(options):
            # 选中目标后清屏，再进入下一轮（展示新目录内容）
            clear_screen()
            current = options[num - 1]
            # 选中上级目录时直接切换；选中无图片的子目录时停留在其中继续选择
            continue
        log("输入无效，请输入列表中的序号。")


def ask_mode(default_copy=True, prompt=input, on_edit=None,
             source_dir=None, supported_ext=(), on_change_dir=None,
             on_tutorial=None):
    """
    程序开始时询问用户采用哪种处理方式；可选择进入「修改配置」「切换目录」或「软件教程」
    :param default_copy: 直接回车时采用的默认值（True=复制，False=移动）
    :param prompt: 读取用户输入的函数（默认 input，便于测试注入）
    :param on_edit: 选择 [3] 修改配置时调用的回调，返回后重新询问；为 None 时不显示该选项
    :param source_dir: 当前源目录；当目录内没有支持的图片时，会提示可切换目录
    :param supported_ext: 支持的扩展名序列，用于判断目录内是否有图片
    :param on_change_dir: 选择 [4] 切换目录时调用的回调，返回后重新询问；为 None 时不显示该选项
    :param on_tutorial: 选择 [5] 软件教程时调用的回调，返回后重新询问；为 None 时不显示该选项
    :return: True=复制原图；False=移动原图；None=用户选择退出
    """
    default_hint = "复制" if default_copy else "移动"

    while True:
        # 每次显示主菜单前清屏，保证从子菜单/切换目录返回后界面干净
        clear_screen()

        # 递归（最多 3 层）判断当前目录是否缺少支持的图片，用于给出提示
        no_supported = (
            source_dir is not None
            and not has_supported_files(source_dir, supported_ext, max_depth=3)
        )

        valid_choices = ["1", "2"]
        menu = colorize("请选择处理方式：", "cyan") + "\n"
        # 显示当前操作目录（源目录），让用户随时确认会对哪个路径操作（黄色高亮）
        if source_dir is not None:
            menu += colorize(f"  当前操作目录：{source_dir}", "yellow") + "\n"
        if no_supported:
            menu += colorize("  [提示] 当前目录没有找到支持的图片文件", "yellow") + "\n"
        menu += (
            colorize("  [1] 复制原图（保留原图，占用额外磁盘空间）", "white") + "\n"
            + colorize("  [2] 移动原图（不保留原图）", "white") + "\n"
        )
        if on_edit is not None:
            menu += colorize("  [3] 修改配置", "white") + "\n"
            valid_choices.append("3")
        if on_change_dir is not None:
            # 切换目录始终可用：即使当前目录有支持的图片，也允许更改目录
            menu += colorize("  [4] 切换目录", "white") + "\n"
            valid_choices.append("4")
        if on_tutorial is not None:
            menu += colorize("  [5] 软件教程", "white") + "\n"
            valid_choices.append("5")
        menu += colorize("  [0] 退出", "white") + "\n"
        valid_choices.append("0")
        tail = "请输入 " + " / ".join(valid_choices)
        tip = (
            menu
            + colorize(tail + "（直接回车默认：", "cyan")
            + colorize(default_hint, "yellow")
            + colorize("）：", "cyan")
        )

        try:
            answer = prompt(tip).strip()
        except EOFError:
            # 非交互环境（无标准输入）：直接采用默认值
            log(f"[提示] 未检测到交互输入，采用默认方式：{default_hint}")
            return default_copy

        if answer == "":
            return default_copy
        if answer == "1":
            return True
        if answer == "2":
            return False
        if answer == "0":
            return None
        if answer == "3" and on_edit is not None:
            on_edit()
            # 返回后回到循环头部，会先清屏再重新显示主菜单
            continue
        if answer == "4" and on_change_dir is not None:
            on_change_dir()
            continue
        if answer == "5" and on_tutorial is not None:
            on_tutorial()
            continue
        log(f"输入无效，请输入 {tail.replace('请输入 ', '')}，或直接回车使用默认值。")
        pause_before_exit(prompt)


class SafeFormatDict(dict):
    """
    用于 str.format_map 的安全字典：缺失的键保持 {key} 原样，不抛 KeyError
    """
    def __missing__(self, key):
        return "{" + key + "}"


def show_tutorial(config, prompt=input):
    """
    显示「软件教程」：从 tutorial.txt 逐行读取内容并打印，回车后返回主菜单
    :param config: 当前配置字典，用于填充教程里的动态占位符（源目录等）
    :param prompt: 读取用户输入的函数（默认 input，便于测试注入）
    """
    clear_screen()

    tutorial_path = get_resource_path("tutorial.txt")
    # 占位符替换用的值；未在模板中出现的键无所谓，缺失的键用空串兜底
    fields = {
        "source_dir": get_source_dir(config),
        "copy_mode": "复制" if config.get("copy_mode", True) else "移动",
        "burst_threshold": config.get("burst_threshold"),
        "supported_ext": "、".join(config.get("supported_ext", [])),
    }

    try:
        with open(tutorial_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        log_colored(f"[错误] 无法读取教程文件：{describe_error(e)}", "red")
        try:
            prompt("按回车键返回主菜单...")
        except EOFError:
            pass
        clear_screen()
        return

    for line in lines:
        # 去掉行尾换行符；用 format_map 替换 {xxx} 占位符，未知字段保持原样
        text = line.rstrip("\n")
        text = text.format_map(SafeFormatDict(fields))
        # 标题行（带 ===== 或 【】）用青色高亮，其余原样输出
        if text.startswith("=====") or (text.startswith("【") and text.endswith("】")):
            log_colored(text, "cyan")
        else:
            log(text)

    log("")
    try:
        prompt("按回车键返回主菜单...")
    except EOFError:
        # 非交互环境：无需等待，直接返回
        pass
    clear_screen()


def pause_before_exit(prompt=input):
    """
    结束后等待用户按回车再退出，避免双击运行时窗口一闪而过看不到结果
    :param prompt: 读取用户输入的函数（默认 input，便于测试注入）
    """
    try:
        prompt("\n按回车键退出...")
    except EOFError:
        # 非交互环境（如管道、重定向）：无输入可等，直接退出
        pass


def main(config_path=CONFIG_FILE, prompt=input):
    """
    命令行入口：读取 JSON 配置、询问处理方式后执行分类
    :param config_path: JSON配置文件路径
    :param prompt: 询问输入的读取函数（默认 input，便于测试注入）
    :return: 成功返回0，出错返回1
    """
    try:
        config = load_config(config_path)

        # 若配置里保存了固定的源目录（非 "." / 空），提示"已加载上次目录"
        saved_source = config.get("source_folder")
        if saved_source not in (None, "", "."):
            log(f"[提示] 已加载上次目录：{os.path.abspath(saved_source)}")

        # 在「选择处理方式」菜单里提供「修改配置」入口；改完重新读取配置
        def on_edit():
            edit_config(config, config_path, prompt)
            config.update(load_config(config_path))

        def on_change_dir():
            """选择 [4] 切换目录：进入文件夹选择菜单，选中后更新配置并保存"""
            new_dir = choose_folder(
                get_source_dir(config), config["supported_ext"], prompt
            )
            if not new_dir:
                return
            config["source_folder"] = new_dir
            try:
                save_config(config, config_path)
                log(f"[完成] 已切换源目录：{new_dir}")
                log("[完成] 已保存至配置文件，下次启动时自动切换到当前目录")
            except OSError as e:
                log(f"[错误] 保存配置失败：{describe_error(e)}")

        def on_tutorial():
            """选择 [5] 软件教程：显示使用说明，回车后返回主菜单"""
            show_tutorial(config, prompt)

        # 主循环：切换目录/修改配置后会重新询问；分类完成后回到菜单再次询问
        while True:
            mode = ask_mode(
                config.get("copy_mode", True), prompt, on_edit=on_edit,
                source_dir=get_source_dir(config),
                supported_ext=config["supported_ext"],
                on_change_dir=on_change_dir,
                on_tutorial=on_tutorial,
            )
            if mode is None:
                # 用户选择 [0] 退出
                break

            config["copy_mode"] = mode
            # 进入分类前清屏，避免菜单与处理日志混在一起
            clear_screen()
            classify_photos(config)
            # 分类结束后暂停，让用户看清结果，再返回主菜单
            pause_before_exit(prompt)

        return 0
    
    except Exception as e:
        log_colored(f"运行出错：{describe_error(e)}", "red")
        return 1


if __name__ == "__main__":
    enable_ansi()
    exit_code = main()
    pause_before_exit()
    sys.exit(exit_code)