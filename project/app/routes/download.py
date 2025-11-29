"""Download API routes."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from ..services import downloader
from ..services.downloader import QUALITY_PRESETS, validate_url
from ..utils.cleanup import delete_path
from ..utils.jobs import create_job, job_status, job_update
from ..utils.ratelimit import allow

router = APIRouter(prefix="/api", tags=["download"])


SUPPORTED_FORMATS = {"mp4", "webm", "mkv", "mp3", "m4a", "ogg", "source"}


@router.post("/download")
async def create_download(
    request: Request,
    url: str = Query(...),
    quality: str = Query("720p"),
    format: str = Query("mp4"),
):
    client_ip = request.client.host if request.client else "unknown"
    if not allow(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    fmt = format.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {fmt}",
        )

    if quality not in QUALITY_PRESETS and quality != "auto":
        raise HTTPException(
            status_code=400,
            detail=f"quality must be one of {sorted(QUALITY_PRESETS)} or 'auto'",
        )

    actual_quality = downloader.DEFAULT_QUALITY if quality == "auto" else quality

    try:
        validate_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = create_job(
        {
            "url": url,
            "quality": actual_quality,
            "format": fmt,
        }
    )
    return {"job_id": job_id}


@router.get("/status/{job_id}")
async def status(job_id: str):
    job = job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    data = {
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "error": job["error"],
        "reason": job.get("reason"),
    }
    if job["status"] == "done" and job.get("result"):
        result = job["result"]
        data["filename"] = result.get("filename")
        data["meta"] = result.get("meta")

    return JSONResponse(data)


@router.get("/file/{job_id}")
async def file(job_id: str, background_tasks: BackgroundTasks):
    job = job_status(job_id)
    if not job or job.get("result") is None or job["status"] != "done":
        raise HTTPException(status_code=404, detail="file not ready")

    result = job["result"]
    background_tasks.add_task(_cleanup_after_download, job_id, result["file_path"])
    return FileResponse(
        path=result["file_path"],
        media_type=result["mimetype"],
        filename=result["filename"],
    )


@router.delete("/file/{job_id}")
async def delete_file(job_id: str):
    job = job_status(job_id)
    if not job or job.get("result") is None:
        raise HTTPException(status_code=404, detail="not found")

    path = job["result"]["file_path"]
    try:
        os.remove(path)
    except FileNotFoundError:
        pass

    job_update(job_id, result=None, status="deleted", message="Файл удалён")
    return {"ok": True}


def _cleanup_after_download(job_id: str, file_path: str) -> None:
    """Remove downloaded file shortly after it is sent to the client."""
    try:
        delete_path(Path(file_path))
    except Exception:
        pass
    job_update(job_id, result=None, status="deleted", message="Файл удалён после скачивания")
