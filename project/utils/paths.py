"""Utility helpers for filenames and mimetypes."""

from __future__ import annotations

import re

SAFE_FILENAME_RE = re.compile(r"[^\w\-. ()\u0400-\u04FF]")


def safe_filename(name: str | None, fallback: str = "file") -> str:
    """
    Produce a sanitized filename suitable for filesystem usage.

    Keeps alphanumeric characters, spaces, dash, underscore, dot, parentheses and Cyrillic letters.
    """
    if not name:
        name = fallback

    sanitized = SAFE_FILENAME_RE.sub("_", name)
    while ".." in sanitized:
        sanitized = sanitized.replace("..", "_")
    sanitized = sanitized.replace("__", "_")
    sanitized = sanitized.strip(" ._")
    return sanitized or fallback


def guess_mimetype(ext: str) -> str:
    ext = ext.lstrip(".").lower()
    if ext in ("mp4", "webm"):
        return f"video/{ext}"
    if ext == "mkv":
        return "video/x-matroska"
    if ext == "mp3":
        return "audio/mpeg"
    if ext == "m4a":
        return "audio/mp4"
    if ext == "ogg":
        return "audio/ogg"
    return "application/octet-stream"


__all__ = ["safe_filename", "guess_mimetype"]
