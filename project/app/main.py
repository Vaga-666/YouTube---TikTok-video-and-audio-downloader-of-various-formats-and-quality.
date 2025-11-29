"""FastAPI application entrypoint."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_fastapi_instrumentator import Instrumentator

from .config import get_settings
from .logging import setup_logging
from .routes.download import router as download_router
from .utils.cleanup import periodic_cleanup
from .utils.jobs import set_backend
from .utils.jobs_memory import MemoryBackend
from .utils.jobs_rq import RQBackend
from .worker import process_job_async

setup_logging()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR.parent / "static"


async def start_worker(queue):
    """Background worker for the in-memory queue."""
    from .utils.jobs import job_status, job_update

    while True:
        job_id = await queue.get()
        try:
            job = job_status(job_id)
            if not job:
                continue
            payload = job.get("payload") or {}

            def updater(**fields):
                job_update(job_id, **fields)

            await process_job_async(job_id, payload, updater)
        except Exception as exc:  # noqa: BLE001
            job_update(job_id, status="error", message=str(exc), error=str(exc))
            logger = logging.getLogger(__name__)
            logger.exception("Memory worker failed for job %s", job_id)
        finally:
            queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown tasks."""
    settings = get_settings()

    worker_task = None
    cleanup_task = None

    if settings.queue_backend == "rq":
        set_backend(RQBackend())
    else:
        memory_backend = MemoryBackend()
        set_backend(memory_backend)
        worker_task = asyncio.create_task(start_worker(memory_backend.queue))
        cleanup_task = asyncio.create_task(
            periodic_cleanup(
                base_dir=settings.tmp_dir,
                ttl_seconds=settings.job_ttl_sec,
                interval_seconds=120,
            )
        )

    try:
        yield
    finally:
        for task in filter(None, (worker_task, cleanup_task)):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="Video Web Bot", version="0.2.0", lifespan=lifespan)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

settings = get_settings()
if settings.cors_origin:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.include_router(download_router)

_CSP_POLICY = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "script-src 'self' https://cdn.tailwindcss.com; "
    "style-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; "
    "font-src 'self' data:; "
    "frame-ancestors 'none'"
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Content-Security-Policy", _CSP_POLICY)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


@app.get("/", include_in_schema=False)
async def read_index(request: Request):
    """Render the landing page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health", include_in_schema=False)
async def healthcheck():
    """Simple health check endpoint."""
    return JSONResponse({"status": "ok"})
