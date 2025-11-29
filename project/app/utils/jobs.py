"""Abstraction layer for job queue backends."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Protocol


class JobBackend(Protocol):
    """Protocol that queue backend implementations must follow."""

    def enqueue(self, payload: Dict[str, Any]) -> str: ...

    def get(self, job_id: str) -> Optional[Dict[str, Any]]: ...

    def set(self, job_id: str, data: Dict[str, Any]) -> None: ...


_backend: Optional[JobBackend] = None


def set_backend(backend: Optional[JobBackend]) -> None:
    """Configure the global job backend instance."""
    global _backend
    _backend = backend


def get_backend() -> Optional[JobBackend]:
    """Return the currently configured backend."""
    return _backend


def create_job(payload: Dict[str, Any]) -> str:
    """Create a job using the configured backend."""
    if _backend is None:
        raise RuntimeError("Job backend is not configured.")
    return _backend.enqueue(payload)


def job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Fetch job data."""
    if _backend is None:
        raise RuntimeError("Job backend is not configured.")
    job = _backend.get(job_id)
    if job is None:
        return None
    return dict(job)


def job_update(job_id: str, **fields: Any) -> Dict[str, Any]:
    """Merge updates into job data."""
    if _backend is None:
        raise RuntimeError("Job backend is not configured.")
    current = _backend.get(job_id) or {}
    current.setdefault("job_id", job_id)
    current.update(fields)
    current["updated_at"] = time.time()
    _backend.set(job_id, current)
    return current
