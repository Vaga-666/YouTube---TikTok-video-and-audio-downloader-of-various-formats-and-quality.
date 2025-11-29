"""RQ worker entrypoint and shared processing logic."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict

from .config import get_settings
from .services import downloader
from .services.converter import convert_any
from .utils.jobs_rq import RQBackend
from .utils.paths import guess_mimetype

logger = logging.getLogger(__name__)

ALLOWED_FORMATS = {"mp4", "webm", "mkv", "mp3", "m4a", "ogg", "source"}


async def process_job_async(
    job_id: str,
    payload: Dict[str, Any],
    update: Callable[..., None],
) -> None:
    """Shared job processing pipeline used by both memory and RQ workers."""
    settings = get_settings()

    url = payload.get("url")
    if not url:
        update(status="error", message="URL отсутствует.", error="missing_url")
        return

    want = (payload.get("want") or payload.get("format") or "mp4").lower()
    if want not in ALLOWED_FORMATS:
        update(
            status="error",
            message=f"Формат {want!r} не поддерживается.",
            error="unsupported_format",
        )
        return

    quality = payload.get("quality", downloader.DEFAULT_QUALITY)
    target_height = downloader.quality_to_height(quality)
    output_dir = Path(settings.tmp_dir) / job_id

    try:
        update(status="fetching", message="Получаю метаданные", progress=5)
        meta = downloader.probe(url, target_height=target_height)
        update(meta=meta)
        downloader.check_size_or_fail(
            meta.get("estimated_size_mb"),
            settings.max_file_size_mb,
        )

        update(status="downloading", message="Скачиваю медиаконтент...", progress=15)

        def hook(data: Dict[str, Any]) -> None:
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            done = data.get("downloaded_bytes") or 0
            if total:
                percent = int(15 + (done / total) * 70)
                update(progress=min(90, max(20, percent)))

        downloaded_path_str = await asyncio.to_thread(
            downloader.download_video,
            url,
            str(output_dir),
            hook,
            quality,
        )
        source_path = Path(downloaded_path_str)
        downloader.ensure_size_within_limit(source_path, settings.max_file_size_mb)

        final_path = source_path
        mimetype = guess_mimetype(source_path.suffix)

        if want == "source":
            final_path = source_path
            mimetype = guess_mimetype(source_path.suffix)
        elif want in ALLOWED_FORMATS:
            is_video_format = want in {"mp4", "webm", "mkv"}
            converting_progress = 95 if is_video_format else 92
            update(
                status="converting",
                message=f"Конвертация в {want.upper()}...",
                progress=converting_progress,
            )
            final_path = convert_any(source_path, want)
            mimetype = guess_mimetype(final_path.suffix)
            if final_path != source_path:
                try:
                    source_path.unlink(missing_ok=True)
                except OSError:
                    pass
        else:
            update(
                status="error",
                message=f"Формат {want} не поддерживается.",
                error="unsupported_format",
            )
            return

        update(
            status="done",
            message="Файл готов к скачиванию.",
            progress=100,
            result={
                "file_path": str(final_path),
                "filename": final_path.name,
                "mimetype": mimetype,
                "meta": meta,
            },
            file_path=str(final_path),
            filename=final_path.name,
            mimetype=mimetype,
        )
        logger.info("Job %s completed", job_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", job_id)
        update(status="error", message=str(exc), error=str(exc))


def run_job(job_id: str) -> None:
    """Entry point executed by RQ worker processes."""
    backend = RQBackend()
    job = backend.get(job_id)
    if not job:
        logger.warning("Job %s not found in Redis", job_id)
        return

    payload: Dict[str, Any] = job.get("payload") or {}

    def update(**fields):
        current = backend.get(job_id) or {}
        current.update(fields)
        backend.set(job_id, current)

    asyncio.run(process_job_async(job_id, payload, update))
