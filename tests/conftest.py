"""pytest 共享夹具：构造带 EXIF 时间的测试图片、隔离的配置与目录。"""

import json
import os
import sys

import piexif
import pytest
from PIL import Image

# 让测试直接导入项目根目录下的 Picchooser.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import Picchooser as P  # noqa: E402


def make_jpeg(path, capture_time=None, size=(64, 64), color=(200, 100, 50)):
    """
    生成一张 JPEG 测试图片。

    :param path: 输出路径
    :param capture_time: EXIF 拍摄时间 "YYYY:MM:DD HH:MM:SS"；None 表示不写 EXIF
    :return: 输出路径
    """
    img = Image.new("RGB", size, color)
    if capture_time is None:
        img.save(path)
        return path

    exif_bytes = piexif.dump({
        "0th": {piexif.ImageIFD.DateTime: capture_time},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: capture_time},
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    })
    img.save(path, exif=exif_bytes)
    return path


def base_config(**overrides):
    """返回一份以项目默认值为基准、可覆盖任意字段的配置字典。"""
    config = dict(P.DEFAULT_CONFIG)
    config.update(overrides)
    return config


@pytest.fixture
def source_dir(tmp_path):
    """空的源目录。"""
    d = tmp_path / "source"
    d.mkdir()
    return d


@pytest.fixture
def config_for(source_dir):
    """返回工厂函数：为临时源目录生成配置字典。"""
    def _make(**overrides):
        defaults = {"source_folder": str(source_dir), "dest_folder": None}
        defaults.update(overrides)
        return base_config(**defaults)
    return _make


@pytest.fixture
def write_config(tmp_path):
    """把配置写入临时 JSON 文件，返回该文件路径。"""
    def _write(config, name="photo_config.json"):
        path = tmp_path / name
        path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return str(path)
    return _write


@pytest.fixture(autouse=True)
def _quiet_log(monkeypatch):
    """默认静音日志，避免测试输出被中文日志淹没。"""
    monkeypatch.setattr(P, "log", lambda message: None)