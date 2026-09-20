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
    """输出到控制台（命令行调用，立即刷新）"""
    print(message, flush=True)


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
            log(f"[提示] 目录里有 {len(skipped_files)} 个文件，但没有一个是支持的图片格式")
            log(f"       当前支持的格式：{'、'.join(config['supported_ext'])}")
            log('       可修改配置 supported_ext 添加格式（例如 ".png"、".heic"）后重试')
        else:
            log(f"[提示] 源目录里没有找到任何文件：{source_dir}")
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
    log("\n" + "=" * 40)
    log(summary)
    log("=" * 40)
    return summary


def ask_mode(default_copy=True, prompt=input):
    """
    程序开始时询问用户采用哪种处理方式
    :param default_copy: 直接回车时采用的默认值（True=复制，False=移动）
    :param prompt: 读取用户输入的函数（默认 input，便于测试注入）
    :return: True=复制原图；False=移动原图
    """
    default_hint = "复制" if default_copy else "移动"
    tip = (
        "请选择处理方式：\n"
        "  [1] 复制原图（保留原图，占用额外磁盘空间）\n"
        "  [2] 移动原图（不保留原图）\n"
        f"请输入 1 或 2（直接回车默认：{default_hint}）："
    )
    while True:
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
        log("输入无效，请输入 1 或 2，或直接回车使用默认值。")


def main(config_path=CONFIG_FILE, prompt=input):
    """
    命令行入口：读取 JSON 配置、询问处理方式后执行分类
    :param config_path: JSON配置文件路径
    :param prompt: 询问输入的读取函数（默认 input，便于测试注入）
    :return: 成功返回0，出错返回1
    """
    try:
        config = load_config(config_path)
        config["copy_mode"] = ask_mode(config.get("copy_mode", True), prompt)
        classify_photos(config)
        return 0
    except Exception as e:
        print(f"运行出错：{describe_error(e)}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())