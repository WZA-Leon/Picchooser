import os
import sys
import json
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
    "copy_mode": True,                        # True=硬链接（保留原图，不占额外空间）；False=移动
    "fallback_copy": True,                    # 硬链接不可用时（跨盘/不支持）是否退回复制
    "burst_threshold": 1.0,                   # 连拍时间阈值（秒）
    "supported_ext": [".jpg", ".jpeg", ".JPG", ".JPEG"],  # 支持的图片格式
    "burst_folder_prefix": "连拍",            # 连拍文件夹前缀
    "single_folder_name": "孤立照片",          # 单张照片文件夹
    "no_exif_folder_name": "无拍摄信息",       # 读不到EXIF的文件夹
}

def log(message):
    """输出到控制台（命令行调用，立即刷新）"""
    print(message, flush=True)


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


def is_same_file(source_path, target_path):
    """
    判断两个路径是否指向同一个文件（同一个硬链接）
    用 inode / 文件索引号比较，Windows 与 POSIX 均适用
    :return: 相同返回True；无法判断返回False
    """
    try:
        return os.path.samefile(source_path, target_path)
    except OSError:
        return False


def link_file(source_path, target_path, fallback_copy=True):
    """
    为源文件创建硬链接到目标路径（保留原图，且不占用额外磁盘空间）
    硬链接不可用时（跨盘、文件系统不支持、无权限等），可选择退回复制
    :param source_path: 源文件完整路径
    :param target_path: 目标文件完整路径
    :param fallback_copy: True=硬链接失败时退回复制；False=直接报错
    :return: "link" = 已建立硬链接；"copy" = 已退回复制
    :raises OSError: 硬链接失败且不允许退回复制
    """
    # 目标已存在：已是同一硬链接则无需处理；否则删除后重建，避免 FileExistsError
    if os.path.exists(target_path):
        if is_same_file(source_path, target_path):
            return "link"
        os.remove(target_path)

    try:
        os.link(source_path, target_path)
        return "link"
    except OSError as e:
        if not fallback_copy:
            raise
        log(f"[警告] 硬链接失败，改为复制：{os.path.basename(source_path)}（{e}）")
        shutil.copy2(source_path, target_path)
        return "copy"


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
    fallback_copy = config["fallback_copy"]
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
        return f"源目录不存在：\n{source_dir}"

    # ---------- 第一步：遍历源目录，收集所有图片和拍摄时间 ----------
    photo_with_time = []  # 格式：(拍摄时间, 文件完整路径, 文件名)
    no_exif_files = []    # 读不到EXIF的文件列表

    for filename in os.listdir(source_dir):
        file_full_path = os.path.join(source_dir, filename)
        if not os.path.isfile(file_full_path):
            continue
        if not filename.endswith(supported_ext):
            continue

        capture_time = get_capture_time(file_full_path)
        if capture_time is not None:
            photo_with_time.append((capture_time, file_full_path, filename))
        else:
            no_exif_files.append(file_full_path)

    if not photo_with_time and not no_exif_files:
        return "源目录中未找到支持的图片文件"

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
    os.makedirs(dest_dir, exist_ok=True)
    burst_index = 0
    link_count = 0   # 成功建立硬链接的数量
    copy_count = 0   # 退回复制的数量

    single_folder = os.path.join(dest_dir, single_folder_name)
    no_exif_folder = os.path.join(dest_dir, no_exif_folder_name)

    def dispatch(file_path, target_folder):
        """把文件放入目标文件夹：copy_mode 时建硬链接，否则移动原图"""
        nonlocal link_count, copy_count
        target_path = os.path.join(target_folder, os.path.basename(file_path))
        if copy_mode:
            if link_file(file_path, target_path, fallback_copy) == "link":
                link_count += 1
            else:
                copy_count += 1
        else:
            shutil.move(file_path, target_path)

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
        mode_line = f"处理方式：硬链接 {link_count} 张"
        if copy_count:
            mode_line += f"（其中 {copy_count} 张退回复制）"
        mode_line += "\n"
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


def main(config_path=CONFIG_FILE):
    """
    命令行入口：读取 JSON 配置后执行分类
    :param config_path: JSON配置文件路径
    :return: 成功返回0，出错返回1
    """
    try:
        config = load_config(config_path)
        classify_photos(config)
        return 0
    except Exception as e:
        print(f"运行出错：{e}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())