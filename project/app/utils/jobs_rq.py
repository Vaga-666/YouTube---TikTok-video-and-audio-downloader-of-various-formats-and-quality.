"""Redis-backed job backend using RQ and application settings."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, Optional

import redis
from rq import Queue

from ..config import get_settings

KEY_TEMPLATE = "job:{id}"


def _key(job_id: str) -> str:
    return KEY_TEMPLATE.format(id=job_id)


class RQBackend:
    """Queue backend powered by Redis/RQ."""

    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.redis = redis.from_url(settings.redis_url)
        self.queue = Queue(
            name=settings.rq_queue,
            connection=self.redis,
            default_timeout=settings.rq_job_ttl_sec,
            result_ttl=settings.rq_result_ttl_sec,
            failure_ttl=settings.rq_failure_ttl_sec,
        )

    def enqueue(self, payload: Dict[str, Any]) -> str:
        """Create job metadata and enqueue worker task."""
        job_id = uuid.uuid4().hex
        now = time.time()
        data = {
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
            "created_at": now,
            "updated_at": now,
            "payload": payload,
        }
        ttl = self.settings.rq_result_ttl_sec
        self.redis.set(_key(job_id), json.dumps(data, ensure_ascii=False), ex=ttl)
        self.queue.enqueue(
            "project.app.worker.run_job",
            job_id,
            job_timeout=self.settings.rq_job_ttl_sec,
            result_ttl=self.settings.rq_result_ttl_sec,
            failure_ttl=self.settings.rq_failure_ttl_sec,
            job_id=job_id,
        )
        return job_id

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        raw = self.redis.get(_key(job_id))
        return None if not raw else json.loads(raw)

    def set(self, job_id: str, data: Dict[str, Any]) -> None:
        ttl = self.settings.rq_result_ttl_sec
        self.redis.set(_key(job_id), json.dumps(data, ensure_ascii=False), ex=ttl)
