"""Helpers for validating, probing, and downloading media."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

from ..config import get_settings
from ..utils.paths import safe_filename

logger = logging.getLogger(__name__)

_SETTINGS = get_settings()

QUALITY_PRESETS = {
    "360p": 360,
    "480p": 480,
    "720p": 720,
    "1024p": 1024,
    "1080p": 1080,
}
DEFAULT_QUALITY = "720p"


def quality_to_height(quality: str) -> int:
    """Translate a quality label to a numeric height."""
    return QUALITY_PRESETS.get(quality, QUALITY_PRESETS[DEFAULT_QUALITY])


def validate_url(url: str) -> None:
    """Ensure the URL has an allowed scheme and domain."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Недопустимая схема URL")

    host = (parsed.hostname or "").lower()
    allowed = _SETTINGS.allowed_domains
    if not any(host == d or host.endswith(f".{d}") for d in allowed):
        raise ValueError("Ссылка с неподдерживаемого домена")


def _select_estimated_size(info_dict: Dict[str, Any]) -> Optional[int]:
    for key in ("filesize", "filesize_approx"):
        if info_dict.get(key):
            return info_dict.get(key)

    formats = info_dict.get("formats") or []
    for candidate in formats:
        size = candidate.get("filesize") or candidate.get("filesize_approx")
        if size:
            return size
    return None


def _bytes_to_mb(value: Optional[int]) -> Optional[float]:
    if value is None:
        return None
    return round(value / (1024 * 1024), 2)


def probe(url: str, target_height: int = 720) -> Dict[str, Any]:
    """Fetch metadata and estimated size, filtering formats by height."""
    validate_url(url)

    opts = {
        "format": "bestvideo+bestaudio/best",
        "quiet": True,
        "noprogress": True,
        "skip_download": True,
        "noplaylist": True,
        "playlist_items": "1",
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except ExtractorError as exc:
        logger.warning("probe failed for %s (%s), retrying without playlist opts", url, exc)
        fallback_opts = {
            "format": "bestvideo+bestaudio/best",
            "quiet": True,
            "noprogress": True,
            "skip_download": True,
        }
        with YoutubeDL(fallback_opts) as ydl:
            info = ydl.extract_info(url, download=False)

    formats = info.get("formats") or []
    mp4_formats = [
        fmt
        for fmt in formats
        if fmt.get("ext") == "mp4" and (fmt.get("height") or 0) <= target_height
    ]
    mp4_formats.sort(
        key=lambda f: ((f.get("height") or 0), f.get("tbr") or 0),
        reverse=True,
    )

    estimated_bytes = None
    for fmt in mp4_formats:
        estimated_bytes = fmt.get("filesize") or fmt.get("filesize_approx")
        if estimated_bytes:
            break

    if estimated_bytes is None:
        # fallback: take any mp4 format
        for fmt in formats:
            if fmt.get("ext") == "mp4":
                estimated_bytes = fmt.get("filesize") or fmt.get("filesize_approx")
                if estimated_bytes:
                    break

    if estimated_bytes is None:
        estimated_bytes = _select_estimated_size(info)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "estimated_size_mb": _bytes_to_mb(estimated_bytes),
    }


def check_size_or_fail(estimated_size_mb: Optional[float], max_size_mb: int) -> None:
    """Ensure the estimated size does not exceed the configured limit."""
    if estimated_size_mb is None:
        return
    if estimated_size_mb > max_size_mb:
        raise ValueError(
            f"Оценочный размер (~{estimated_size_mb} МБ) превышает лимит {max_size_mb} МБ."
        )


def download_video(
    url: str,
    out_dir: str,
    progress_cb=None,
    quality: str | int | None = DEFAULT_QUALITY,
) -> str:
    """Download video using yt-dlp and return the local file path."""
    validate_url(url)

    tmp_path = Path(out_dir)
    tmp_path.mkdir(parents=True, exist_ok=True)

    fmt = "bestvideo+bestaudio/best"

    ydl_opts = {
        "format": fmt,
        "merge_output_format": "mp4",
        "outtmpl": str(tmp_path / "%(title)s.%(ext)s"),
        "quiet": True,
        "noprogress": True,
        "noplaylist": True,
        "playlist_items": "1",
        "progress_hooks": [progress_cb] if progress_cb else [],
    }

    logger.info("download_video url=%s quality=%s format=%s", url, quality, fmt)

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = Path(ydl.prepare_filename(info))
    except DownloadError as exc:
        logger.warning("Primary format failed (%s). Retrying with generic 'best'.", exc)
        fallback_opts = dict(ydl_opts)
        fallback_opts["format"] = "best"
        fallback_opts.pop("merge_output_format", None)
        with YoutubeDL(fallback_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = Path(ydl.prepare_filename(info))

    if not downloaded_path.exists() and info.get("ext"):
        candidate = downloaded_path.with_suffix(f".{info['ext']}")
        if candidate.exists():
            downloaded_path = candidate

    if not downloaded_path.exists():
        raise RuntimeError("Не удалось определить путь к загруженному файлу.")

    title = info.get("title")
    if title:
        sanitized = safe_filename(title, fallback=downloaded_path.stem)
        target_path = downloaded_path.with_name(f"{sanitized}{downloaded_path.suffix}")
        if target_path != downloaded_path:
            try:
                if target_path.exists():
                    target_path.unlink()
                downloaded_path = downloaded_path.rename(target_path)
            except OSError:
                logger.debug("Не удалось переименовать файл в безопасное имя", exc_info=True)

    return str(downloaded_path)


def ensure_size_within_limit(path: Path, max_size_mb: int) -> None:
    """Validate file size after download."""
    size_mb = _bytes_to_mb(path.stat().st_size)
    if size_mb and size_mb > max_size_mb:
        raise ValueError(
            f"Размер файла {size_mb} МБ превышает лимит {max_size_mb} МБ."
        )


__all__ = [
    "QUALITY_PRESETS",
    "DEFAULT_QUALITY",
    "quality_to_height",
    "validate_url",
    "probe",
    "check_size_or_fail",
    "download_video",
    "ensure_size_within_limit",
]
