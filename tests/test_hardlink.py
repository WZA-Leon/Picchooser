"""硬链接核心逻辑测试：link_file / is_same_file。"""

import os

import pytest

import Picchooser as P

from conftest import make_jpeg


def link_count(path):
    """返回该文件在文件系统上的硬链接数量（跨平台）。"""
    stat = os.stat(path)
    # Windows 的 st_nlink 即为硬链接数，POSIX 同理
    return stat.st_nlink


class TestIsSameFile:
    def test_true_for_source_and_link(self, tmp_path):
        src = make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        dst = tmp_path / "link.jpg"
        os.link(src, dst)
        assert P.is_same_file(str(src), str(dst)) is True

    def test_false_for_independent_copies(self, tmp_path):
        src = make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        dst = tmp_path / "copy.jpg"
        dst.write_bytes(src.read_bytes())
        assert P.is_same_file(str(src), str(dst)) is False

    def test_false_when_path_missing(self, tmp_path):
        src = make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        assert P.is_same_file(str(src), str(tmp_path / "ghost.jpg")) is False


class TestLinkFile:
    def test_creates_hard_link(self, tmp_path):
        src = make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        dst = tmp_path / "out" / "a.jpg"
        dst.parent.mkdir()

        assert P.link_file(str(src), str(dst)) == "link"
        assert dst.exists()
        # 关键断言：两者是同一份数据，而不是两份拷贝
        assert os.path.samefile(str(src), str(dst))
        assert link_count(str(src)) == 2

    def test_original_survives(self, tmp_path):
        src = make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        dst = tmp_path / "out" / "a.jpg"
        dst.parent.mkdir()
        P.link_file(str(src), str(dst))
        assert src.exists()
        assert src.read_bytes() == dst.read_bytes()

    def test_reports_copy_when_link_unavailable(self, tmp_path, monkeypatch):
        src = make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        dst = tmp_path / "out" / "a.jpg"
        dst.parent.mkdir()

        def boom(a, b, **kwargs):
            raise OSError(1, "simulated cross-device link")

        monkeypatch.setattr(os, "link", boom)
        assert P.link_file(str(src), str(dst), fallback_copy=True) == "copy"
        assert dst.exists()
        assert not os.path.samefile(str(src), str(dst))
        assert link_count(str(src)) == 1

    def test_raises_when_fallback_disabled(self, tmp_path, monkeypatch):
        src = make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        dst = tmp_path / "out" / "a.jpg"
        dst.parent.mkdir()

        def boom(a, b, **kwargs):
            raise OSError(1, "simulated cross-device link")

        monkeypatch.setattr(os, "link", boom)
        with pytest.raises(OSError):
            P.link_file(str(src), str(dst), fallback_copy=False)
        assert not dst.exists()

    def test_idempotent_for_same_file(self, tmp_path):
        """目标已是同一硬链接时重复调用应安全返回，且不增加链接数。"""
        src = make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        dst = tmp_path / "out" / "a.jpg"
        dst.parent.mkdir()

        assert P.link_file(str(src), str(dst)) == "link"
        assert P.link_file(str(src), str(dst)) == "link"
        assert link_count(str(src)) == 2

    def test_existing_different_target_is_replaced(self, tmp_path):
        """目标已存在但内容不同时，应替换而不是抛 FileExistsError。"""
        src = make_jpeg(tmp_path / "src.jpg", "2024:05:01 10:00:00")
        dst = make_jpeg(tmp_path / "dst.jpg", "2020:01:01 00:00:00")
        assert not os.path.samefile(str(src), str(dst))

        assert P.link_file(str(src), str(dst)) == "link"
        assert os.path.samefile(str(src), str(dst))
        assert dst.read_bytes() == src.read_bytes()

    def test_deleting_link_keeps_original(self, tmp_path):
        """删除分类结果不应影响原图（硬链接语义）。"""
        src = make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        dst = tmp_path / "out" / "a.jpg"
        dst.parent.mkdir()
        P.link_file(str(src), str(dst))

        os.remove(dst)
        assert src.exists()
        assert link_count(str(src)) == 1

    def test_does_not_duplicate_disk_usage(self, tmp_path, monkeypatch):
        """硬链接不应额外占用空间：写入链接即等于写入原图。"""
        src = make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        dst = tmp_path / "out" / "a.jpg"
        dst.parent.mkdir()
        P.link_file(str(src), str(dst))
        # 同一份数据：修改其中一个，另一个同步可见
        with open(src, "ab") as f:
            f.write(b"tail")
        assert dst.stat().st_size == src.stat().st_size