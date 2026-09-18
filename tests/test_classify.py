"""照片分类端到端测试：分组、硬链接落盘、移动模式。"""

import os

import Picchooser as P

from conftest import make_jpeg

BURST = P.DEFAULT_CONFIG["burst_folder_prefix"]
SINGLE = P.DEFAULT_CONFIG["single_folder_name"]
NOEXIF = P.DEFAULT_CONFIG["no_exif_folder_name"]


def results(source_dir):
    """返回 分类结果 目录路径。"""
    return source_dir / "分类结果"


class TestEmptyAndInvalid:
    def test_empty_directory(self, source_dir, config_for):
        assert P.classify_photos(config_for()) == "源目录中未找到支持的图片文件"

    def test_missing_source_directory(self, tmp_path, config_for):
        config = config_for(source_folder=str(tmp_path / "nope"))
        assert P.classify_photos(config).startswith("源目录不存在")

    def test_ignores_unsupported_extensions(self, source_dir, config_for):
        (source_dir / "note.txt").write_text("hello", encoding="utf-8")
        (source_dir / "raw.cr2").write_bytes(b"x")
        assert P.classify_photos(config_for()) == "源目录中未找到支持的图片文件"


class TestGrouping:
    def test_burst_photos_go_to_burst_folder(self, source_dir, config_for):
        for i, ts in enumerate(
            ["2024:05:01 10:00:00", "2024:05:01 10:00:01", "2024:05:01 10:00:02"]
        ):
            make_jpeg(source_dir / f"IMG_{i:03d}.jpg", ts)

        summary = P.classify_photos(config_for(burst_threshold=3))

        burst = results(source_dir) / f"{BURST}1"
        assert sorted(p.name for p in burst.iterdir()) == ["IMG_000.jpg", "IMG_001.jpg", "IMG_002.jpg"]
        assert "连拍组：1 组" in summary

    def test_isolated_photo_goes_to_single_folder(self, source_dir, config_for):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        make_jpeg(source_dir / "b.jpg", "2024:05:01 18:00:00")

        P.classify_photos(config_for(burst_threshold=3))

        single = results(source_dir) / SINGLE
        assert sorted(p.name for p in single.iterdir()) == ["a.jpg", "b.jpg"]

    def test_photo_without_exif_goes_to_noexif_folder(self, source_dir, config_for):
        make_jpeg(source_dir / "noexif.jpg")
        P.classify_photos(config_for())

        folder = results(source_dir) / NOEXIF
        assert [p.name for p in folder.iterdir()] == ["noexif.jpg"]

    def test_mixed_scenario(self, source_dir, config_for):
        # 一组 3 张连拍 + 1 张孤立 + 1 张无 EXIF
        for i, ts in enumerate(
            ["2024:05:01 10:00:00", "2024:05:01 10:00:01", "2024:05:01 10:00:02"]
        ):
            make_jpeg(source_dir / f"B{i}.jpg", ts)
        make_jpeg(source_dir / "solo.jpg", "2024:05:01 15:30:00")
        make_jpeg(source_dir / "noexif.jpg")

        summary = P.classify_photos(config_for(burst_threshold=3))

        assert len(list((results(source_dir) / f"{BURST}1").iterdir())) == 3
        assert len(list((results(source_dir) / SINGLE).iterdir())) == 1
        assert len(list((results(source_dir) / NOEXIF).iterdir())) == 1
        assert "共处理 5 张图片" in summary
        assert "连拍组：1 组" in summary
        assert "孤立照片：1 张" in summary
        assert "无拍摄信息：1 张" in summary

    def test_two_separate_bursts_get_numbered_folders(self, source_dir, config_for):
        times = [
            "2024:05:01 10:00:00", "2024:05:01 10:00:01",   # 连拍1
            "2024:05:01 16:00:00", "2024:05:01 16:00:01",   # 连拍2
        ]
        for i, ts in enumerate(times):
            make_jpeg(source_dir / f"IMG_{i}.jpg", ts)

        summary = P.classify_photos(config_for(burst_threshold=3))

        assert (results(source_dir) / f"{BURST}1").is_dir()
        assert (results(source_dir) / f"{BURST}2").is_dir()
        assert "连拍组：2 组" in summary

    def test_threshold_boundary_is_inclusive(self, source_dir, config_for):
        """间隔恰好等于阈值时视为同一组连拍。"""
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        make_jpeg(source_dir / "b.jpg", "2024:05:01 10:00:03")
        P.classify_photos(config_for(burst_threshold=3))
        assert (results(source_dir) / f"{BURST}1").is_dir()

    def test_just_over_threshold_splits(self, source_dir, config_for):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        make_jpeg(source_dir / "b.jpg", "2024:05:01 10:00:04")
        P.classify_photos(config_for(burst_threshold=3))
        assert not (results(source_dir) / f"{BURST}1").exists()

    def test_unsorted_input_is_sorted_by_time(self, source_dir, config_for):
        """文件名顺序与拍摄顺序无关时，仍按时间分组。"""
        make_jpeg(source_dir / "z.jpg", "2024:05:01 10:00:00")
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:01")
        make_jpeg(source_dir / "m.jpg", "2024:05:01 10:00:02")
        P.classify_photos(config_for(burst_threshold=3))
        assert len(list((results(source_dir) / f"{BURST}1").iterdir())) == 3

    def test_custom_folder_names(self, source_dir, config_for):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        make_jpeg(source_dir / "b.jpg", "2024:05:01 10:00:01")
        P.classify_photos(config_for(
            burst_threshold=3,
            burst_folder_prefix="Burst",
            single_folder_name="Single",
            no_exif_folder_name="NoExif",
        ))
        assert (results(source_dir) / "Burst1").is_dir()


class TestDestFolder:
    def test_default_dest_is_inside_source(self, source_dir, config_for):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        summary = P.classify_photos(config_for())
        assert str(results(source_dir)) in summary

    def test_explicit_dest_folder(self, source_dir, tmp_path, config_for):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        dest = tmp_path / "custom_out"
        P.classify_photos(config_for(dest_folder=str(dest)))
        assert dest.is_dir()
        assert (dest / SINGLE / "a.jpg").exists()


class TestHardLinkMode:
    def test_results_are_hard_links_to_originals(self, source_dir, config_for):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        make_jpeg(source_dir / "b.jpg", "2024:05:01 10:00:01")

        P.classify_photos(config_for(burst_threshold=3))

        linked = results(source_dir) / f"{BURST}1" / "a.jpg"
        assert os.path.samefile(str(source_dir / "a.jpg"), str(linked))
        assert os.stat(str(source_dir / "a.jpg")).st_nlink == 2

    def test_originals_remain_in_source(self, source_dir, config_for):
        for i in range(3):
            make_jpeg(source_dir / f"IMG_{i}.jpg", f"2024:05:01 10:00:0{i}")

        P.classify_photos(config_for(burst_threshold=3))

        remaining = {p.name for p in source_dir.iterdir() if p.suffix == ".jpg"}
        assert remaining == {"IMG_0.jpg", "IMG_1.jpg", "IMG_2.jpg"}

    def test_summary_reports_hardlink_count(self, source_dir, config_for):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        make_jpeg(source_dir / "b.jpg", "2024:05:01 10:00:01")
        summary = P.classify_photos(config_for(burst_threshold=3))
        assert "处理方式：硬链接 2 张" in summary

    def test_summary_reports_copy_fallback(self, source_dir, config_for, monkeypatch):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        make_jpeg(source_dir / "b.jpg", "2024:05:01 10:00:01")

        def boom(a, b, **kwargs):
            raise OSError(1, "simulated cross-device link")

        monkeypatch.setattr(os, "link", boom)
        summary = P.classify_photos(config_for(burst_threshold=3, fallback_copy=True))
        assert "退回复制" in summary

    def test_rerun_is_safe_and_keeps_single_link(self, source_dir, config_for):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        config = config_for()

        P.classify_photos(config)
        before = os.stat(str(source_dir / "a.jpg")).st_nlink
        P.classify_photos(config)
        after = os.stat(str(source_dir / "a.jpg")).st_nlink

        assert before == after == 2


class TestMoveMode:
    def test_move_mode_removes_originals(self, source_dir, config_for):
        for i in range(3):
            make_jpeg(source_dir / f"IMG_{i}.jpg", f"2024:05:01 10:00:0{i}")

        summary = P.classify_photos(config_for(burst_threshold=3, copy_mode=False))

        assert not [p for p in source_dir.iterdir() if p.suffix == ".jpg"]
        assert len(list((results(source_dir) / f"{BURST}1").iterdir())) == 3
        assert "处理方式：移动原图" in summary

    def test_move_mode_does_not_create_links(self, source_dir, config_for):
        make_jpeg(source_dir / "a.jpg", "2024:05:01 10:00:00")
        P.classify_photos(config_for(copy_mode=False))
        moved = results(source_dir) / SINGLE / "a.jpg"
        assert moved.exists()
        assert os.stat(str(moved)).st_nlink == 1