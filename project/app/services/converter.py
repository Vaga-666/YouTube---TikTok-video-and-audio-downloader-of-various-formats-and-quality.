"""Audio/video conversion helpers."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

VIDEO_PRESETS = {
    "mp4": ["-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart"],
    "webm": ["-c:v", "libvpx-vp9", "-c:a", "libopus"],
    "mkv": ["-c:v", "libx264", "-c:a", "aac"],
}

AUDIO_PRESETS = {
    "mp3": ["-vn", "-c:a", "libmp3lame", "-b:a", "192k"],
    "m4a": ["-vn", "-c:a", "aac", "-b:a", "192k"],
    "ogg": ["-vn", "-c:a", "libvorbis", "-q:a", "4"],
}


def run_ffmpeg(input_path: Path, output_path: Path, args: list[str]) -> Path:
    cmd = ["ffmpeg", "-y", "-i", str(input_path), *args, str(output_path)]
    logger.info("ffmpeg: %s", " ".join(cmd))
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        err = result.stderr.decode(errors="ignore")
        logger.error("ffmpeg failed: %s", err)
        raise RuntimeError("ffmpeg conversion failed")
    return output_path


def convert_any(input_path: Path, target_format: str) -> Path:
    """
    Конвертация медиа в нужный формат.

    Если формат совпадает с исходным — создаётся новый файл с суффиксом `_conv`
    во избежание перезаписи оригинала.
    """
    target_format = (target_format or "").lower()
    if target_format == "source" or not target_format:
        return input_path

    if input_path.suffix.lower() == f".{target_format}":
        output_path = input_path.with_name(f"{input_path.stem}_conv.{target_format}")
    else:
        output_path = input_path.with_suffix(f".{target_format}")

    if target_format in VIDEO_PRESETS:
        args = VIDEO_PRESETS[target_format]
    elif target_format in AUDIO_PRESETS:
        args = AUDIO_PRESETS[target_format]
    else:
        raise ValueError(f"Unsupported target format: {target_format}")

    return run_ffmpeg(input_path, output_path, args)


def to_mp3(source: Path) -> Path:
    return convert_any(source, "mp3")


__all__ = ["convert_any", "run_ffmpeg", "to_mp3"]
