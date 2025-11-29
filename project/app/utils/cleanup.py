"""Helpers for cleaning up temporary files."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Iterable


async def remove_file_after_delay(path: Path, delay_seconds: int) -> None:
    """Remove a file after the specified delay."""
    await asyncio.sleep(delay_seconds)
    delete_path(path)


def delete_path(path: Path) -> None:
    """Delete a path if it exists and remove empty parent folders."""
    try:
        if path.is_file():
            path.unlink(missing_ok=True)
        elif path.exists():
            for child in path.iterdir():
                delete_path(child)
            path.rmdir()
    except OSError:
        # Silently ignore filesystem issues; periodic cleanup will retry.
        pass


def cleanup_expired_files(base_dir: Path, ttl_seconds: int) -> None:
    """Remove files older than the TTL inside the temporary directory."""
    if not base_dir.exists():
        return

    now = time.time()
    for path in _iter_all_paths(base_dir):
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue

        if age > ttl_seconds:
            delete_path(path)


def _iter_all_paths(directory: Path) -> Iterable[Path]:
    for child in directory.iterdir():
        if child.is_dir():
            yield from _iter_all_paths(child)
        yield child


async def periodic_cleanup(
    base_dir: Path,
    ttl_seconds: int,
    interval_seconds: int = 300,
) -> None:
    """Periodically cleanup expired files."""
    while True:
        cleanup_expired_files(base_dir, ttl_seconds)
        await asyncio.sleep(interval_seconds)
