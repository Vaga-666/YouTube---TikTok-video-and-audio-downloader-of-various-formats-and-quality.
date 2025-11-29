from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import converter


def _mock_run(monkeypatch, marker, tracker=None):
    def fake_run(cmd, stdout=None, stderr=None, **kwargs):
        if tracker is not None:
            tracker["cmd"] = cmd
        Path(cmd[-1]).write_bytes(marker)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=b"")

    monkeypatch.setattr(converter.subprocess, "run", fake_run)


def test_convert_any_video(monkeypatch, tmp_path):
    input_path = tmp_path / "video.mkv"
    input_path.write_bytes(b"data")
    _mock_run(monkeypatch, b"mp4")

    output = converter.convert_any(input_path, "mp4")
    assert output.exists()
    assert output.suffix == ".mp4"
    assert output.read_bytes() == b"mp4"


def test_convert_any_audio(monkeypatch, tmp_path):
    input_path = tmp_path / "audio.wav"
    input_path.write_bytes(b"data")
    _mock_run(monkeypatch, b"mp3")

    output = converter.convert_any(input_path, "mp3")
    assert output.exists()
    assert output.suffix == ".mp3"
    assert output.read_bytes() == b"mp3"


def test_convert_any_source_returns_same(tmp_path):
    input_path = tmp_path / "file.bin"
    input_path.write_bytes(b"data")
    assert converter.convert_any(input_path, "source") == input_path


def test_convert_any_same_extension_creates_conv_file(monkeypatch, tmp_path):
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"data")

    tracker = {}
    _mock_run(monkeypatch, b"mp4", tracker)

    output = converter.convert_any(input_path, "mp4")
    assert output.exists()
    assert output.name == "video_conv.mp4"
    assert tracker["cmd"][-1].endswith("video_conv.mp4")
    assert output.read_bytes() == b"mp4"


def test_convert_any_invalid_format(tmp_path):
    input_path = tmp_path / "file.bin"
    input_path.write_bytes(b"data")
    with pytest.raises(ValueError):
        converter.convert_any(input_path, "flac")


def test_run_ffmpeg_failure(monkeypatch, tmp_path):
    input_path = tmp_path / "file.bin"
    input_path.write_bytes(b"data")

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stderr=b"error")

    monkeypatch.setattr(converter.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        converter.convert_any(input_path, "mp3")
