"""EXIF 拍摄时间解析测试。"""

import datetime

import Picchooser as P

from conftest import make_jpeg


class TestGetCaptureTime:
    def test_reads_datetime_original(self, tmp_path):
        path = make_jpeg(tmp_path / "a.jpg", "2024:05:01 10:00:00")
        assert P.get_capture_time(str(path)) == datetime.datetime(2024, 5, 1, 10, 0, 0)

    def test_returns_none_without_exif(self, tmp_path):
        path = make_jpeg(tmp_path / "plain.jpg")
        assert P.get_capture_time(str(path)) is None

    def test_returns_none_for_non_image_file(self, tmp_path):
        bogus = tmp_path / "not_an_image.jpg"
        bogus.write_bytes(b"definitely not a jpeg")
        assert P.get_capture_time(str(bogus)) is None

    def test_reads_various_timestamps(self, tmp_path):
        cases = {
            "morning.jpg": "2023:01:02 09:30:15",
            "midnight.jpg": "1999:12:31 23:59:59",
            "leap.jpg": "2024:02:29 12:00:00",
        }
        for name, ts in cases.items():
            path = make_jpeg(tmp_path / name, ts)
            expected = datetime.datetime.strptime(ts, "%Y:%m:%d %H:%M:%S")
            assert P.get_capture_time(str(path)) == expected

    def test_returns_datetime_object(self, tmp_path):
        path = make_jpeg(tmp_path / "t.jpg", "2024:05:01 10:00:00")
        assert isinstance(P.get_capture_time(str(path)), datetime.datetime)