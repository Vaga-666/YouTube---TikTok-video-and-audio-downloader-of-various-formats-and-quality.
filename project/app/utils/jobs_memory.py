"""In-memory job backend implementation."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, Optional


class MemoryBackend:
    """Simple in-memory backend for development and tests."""

    def __init__(self) -> None:
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.queue: "asyncio.Queue[str]" = asyncio.Queue()

    def enqueue(self, payload: Dict[str, Any]) -> str:
        job_id = uuid.uuid4().hex
        now = time.time()
        self.jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0,
            "message": "В очереди",
            "result": None,
            "error": None,
            "reason": None,
            "file_path": None,
            "filename": None,
            "mimetype": None,
            "meta": None,
            "payload": payload,
            "created_at": now,
            "updated_at": now,
        }
        self.queue.put_nowait(job_id)
        return job_id

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self.jobs.get(job_id)
        return dict(job) if job else None

    def set(self, job_id: str, data: Dict[str, Any]) -> None:
        self.jobs[job_id] = dict(data)
