"""命令行入口 main() 测试。"""

import Picchooser as P

from conftest import make_jpeg


class TestMain:
    def test_returns_zero_on_success(self, source_dir, write_config):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        config = dict(P.DEFAULT_CONFIG, source_folder=str(source_dir))
        assert P.main(write_config(config)) == 0

    def test_returns_zero_on_empty_directory(self, source_dir, write_config):
        """空目录只是没有可处理的图片，不算错误。"""
        config = dict(P.DEFAULT_CONFIG, source_folder=str(source_dir))
        assert P.main(write_config(config)) == 0

    def test_returns_one_on_missing_config(self, tmp_path, monkeypatch):
        """配置缺失时会退回默认值并使用当前目录，仍应正常返回。"""
        monkeypatch.chdir(tmp_path)
        assert P.main(str(tmp_path / "absent.json")) == 0

    def test_returns_one_when_classify_raises(self, write_config, monkeypatch):
        def boom(config):
            raise RuntimeError("simulated failure")

        monkeypatch.setattr(P, "classify_photos", boom)
        assert P.main(write_config({})) == 1

    def test_end_to_end_creates_links(self, source_dir, write_config):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        config = dict(P.DEFAULT_CONFIG, source_folder=str(source_dir), copy_mode=True)
        P.main(write_config(config))

        produced = source_dir / "分类结果" / P.DEFAULT_CONFIG["single_folder_name"] / "a.jpg"
        assert produced.exists()