import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QUEUE_BACKEND", "memory")

from app.config import get_settings  # noqa: E402
from app.utils import jobs, ratelimit  # noqa: E402
from app.utils.jobs_memory import MemoryBackend  # noqa: E402

get_settings.cache_clear()
jobs.set_backend(MemoryBackend())


def _drain_backend(backend: MemoryBackend) -> None:
    while True:
        try:
            backend.queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        else:
            backend.queue.task_done()
    backend.jobs.clear()


@pytest.fixture(autouse=True)
def setup_memory_backend(monkeypatch):
    monkeypatch.setenv("QUEUE_BACKEND", "memory")
    get_settings.cache_clear()
    backend = MemoryBackend()
    jobs.set_backend(backend)
    ratelimit.reset()
    yield
    _drain_backend(backend)
    jobs.set_backend(None)
