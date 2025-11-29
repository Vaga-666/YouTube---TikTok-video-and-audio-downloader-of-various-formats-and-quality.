"""Application bootstrap helpers."""

from __future__ import annotations

from .config import get_settings
from .utils import jobs
from .utils.jobs_memory import MemoryBackend
from .utils.jobs_rq import RQBackend


def configure_job_backend():
    """Initialise the job backend based on settings."""
    backend = jobs.get_backend()
    if backend is not None:
        return backend

    settings = get_settings()
    if settings.queue_backend == "memory":
        backend = MemoryBackend()
    elif settings.queue_backend == "rq":
        backend = RQBackend()
    else:  # pragma: no cover
        raise ValueError(f"Неизвестный QUEUE_BACKEND: {settings.queue_backend}")

    jobs.set_backend(backend)
    return backend
