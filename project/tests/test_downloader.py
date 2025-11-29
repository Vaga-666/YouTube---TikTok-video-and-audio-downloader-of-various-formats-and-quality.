from pathlib import Path
from pathlib import Path

import pytest

from app.services import downloader


def test_validate_url():
    downloader.validate_url("https://www.youtube.com/watch?v=abc")
    with pytest.raises(ValueError):
        downloader.validate_url("ftp://example.com/video")
    with pytest.raises(ValueError):
        downloader.validate_url("https://example.com/video")


def test_quality_to_height():
    assert downloader.quality_to_height("480p") == 480
    assert downloader.quality_to_height("unknown") == downloader.quality_to_height(downloader.DEFAULT_QUALITY)


def test_check_size_or_fail():
    downloader.check_size_or_fail(100, 500)  # within limits
    with pytest.raises(ValueError):
        downloader.check_size_or_fail(600, 500)


def test_probe_returns_metadata(monkeypatch):
    class DummyYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def extract_info(self, url, download):
            assert not download
            return {
                "title": "Sample Video",
                "duration": 120,
                "thumbnail": "https://img.test/thumb.jpg",
                "formats": [
                    {"ext": "mp4", "height": 1080, "filesize": 5 * 1024 * 1024},
                    {"ext": "mp4", "height": 480, "filesize": 2 * 1024 * 1024},
                ],
            }

    monkeypatch.setattr(downloader, "YoutubeDL", DummyYDL)

    meta = downloader.probe("https://www.youtube.com/watch?v=abc", target_height=720)
    assert meta["title"] == "Sample Video"
    assert meta["duration"] == 120
    assert meta["thumbnail"]
    assert meta["estimated_size_mb"] == 2.0


def test_download_video_creates_file(tmp_path, monkeypatch):
    created = []

    class DummyYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def extract_info(self, url, download):
            assert download
            info = {"id": "abc123", "title": "Sample Video", "ext": "mp4"}
            outtmpl = self.opts["outtmpl"]
            file_path = Path(outtmpl.replace("%(ext)s", info["ext"]))
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"content")
            for hook in self.opts.get("progress_hooks", []):
                hook({"status": "downloading", "downloaded_bytes": 512, "total_bytes": 1024})
                hook({"status": "finished"})
            created.append(file_path)
            return info

        def prepare_filename(self, info):
            return self.opts["outtmpl"].replace("%(ext)s", info["ext"])

    monkeypatch.setattr(downloader, "YoutubeDL", DummyYDL)

    result_path = downloader.download_video(
        "https://www.youtube.com/watch?v=abc",
        str(tmp_path),
        None,
        downloader.DEFAULT_QUALITY,
    )
    result = Path(result_path)
    assert result.exists()
    assert result.suffix == ".mp4"
