"""配置加载与默认值测试。"""

import json
import os

import Picchooser as P

from conftest import base_config


class TestDefaultConfig:
    def test_has_all_expected_keys(self):
        expected = {
            "source_folder", "dest_folder", "copy_mode", "fallback_copy",
            "burst_threshold", "supported_ext", "burst_folder_prefix",
            "single_folder_name", "no_exif_folder_name",
        }
        assert expected <= set(P.DEFAULT_CONFIG)

    def test_default_is_hardlink_mode_with_fallback(self):
        assert P.DEFAULT_CONFIG["copy_mode"] is True
        assert P.DEFAULT_CONFIG["fallback_copy"] is True

    def test_supported_ext_covers_upper_and_lower_jpeg(self):
        exts = P.DEFAULT_CONFIG["supported_ext"]
        assert ".jpg" in exts and ".JPG" in exts


class TestLoadConfig:
    def test_missing_file_falls_back_to_defaults(self, tmp_path):
        config = P.load_config(str(tmp_path / "nope.json"))
        assert config == P.DEFAULT_CONFIG

    def test_reads_user_values(self, write_config):
        user = {"copy_mode": False, "burst_threshold": 7}
        path = write_config(user)
        config = P.load_config(path)
        assert config["copy_mode"] is False
        assert config["burst_threshold"] == 7

    def test_partial_config_is_filled_with_defaults(self, write_config):
        path = write_config({"burst_threshold": 5})
        config = P.load_config(path)
        assert config["burst_threshold"] == 5
        # 未提供的键由默认值兜底
        assert config["copy_mode"] == P.DEFAULT_CONFIG["copy_mode"]
        assert config["fallback_copy"] == P.DEFAULT_CONFIG["fallback_copy"]

    def test_broken_json_falls_back_to_defaults(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{ this is not json", encoding="utf-8")
        assert P.load_config(str(bad)) == P.DEFAULT_CONFIG

    def test_does_not_mutate_default_config(self, write_config):
        before = dict(P.DEFAULT_CONFIG)
        P.load_config(write_config({"burst_threshold": 99}))
        assert P.DEFAULT_CONFIG == before

    def test_supports_chinese_folder_names(self, write_config):
        cfg = {"single_folder_name": "孤独的照片", "no_exif_folder_name": "未知时间"}
        config = P.load_config(write_config(cfg))
        assert config["single_folder_name"] == "孤独的照片"
        assert config["no_exif_folder_name"] == "未知时间"


class TestConfigDiscovery:
    def test_prefers_current_working_directory(self, tmp_path, monkeypatch):
        cfg = tmp_path / "photo_config.json"
        cfg.write_text("{}", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert P._find_config() == str(cfg)

    def test_falls_back_to_app_dir_when_cwd_has_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        found = P._find_config()
        assert found == os.path.join(P.get_app_dir(), "photo_config.json")


class TestBaseConfigHelper:
    def test_helper_matches_project_defaults(self):
        assert base_config() == P.DEFAULT_CONFIG

    def test_helper_applies_overrides(self):
        assert base_config(burst_threshold=42)["burst_threshold"] == 42