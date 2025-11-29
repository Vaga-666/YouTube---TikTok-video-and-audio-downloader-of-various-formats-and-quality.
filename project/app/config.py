"""Configuration helpers for the video web bot."""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

try:  # Pydantic v2
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - fallback for Pydantic v1
    from pydantic import BaseSettings  # type: ignore

    SettingsConfigDict = None  # type: ignore

try:
    from pydantic import field_validator
except ImportError:  # pragma: no cover - fallback for Pydantic v1
    from pydantic import validator as _legacy_validator  # type: ignore

    def field_validator(  # type: ignore[misc]
        field_name: str,
        *,
        mode: str = "after",
    ):
        pre = mode == "before"
        return _legacy_validator(field_name, pre=pre)


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    max_file_size_mb: int = 500
    log_level: str = "INFO"
    tmp_dir: Path = Path("./temp")
    allowed_domains: List[str] = ["youtube.com", "youtu.be", "tiktok.com"]
    job_ttl_sec: int = 900
    cors_origin: Optional[str] = None
    queue_backend: str = "memory"
    redis_url: str = "redis://localhost:6379/0"
    rq_queue: str = "downloads"
    rq_job_ttl_sec: int = 1800
    rq_result_ttl_sec: int = 3600
    rq_failure_ttl_sec: int = 86400

    if SettingsConfigDict is not None:  # pragma: no branch
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
        )
    else:  # pragma: no cover - Pydantic v1 fallback
        class Config:  # type: ignore[no-redef]
            env_file = ".env"
            env_file_encoding = "utf-8"

    @field_validator("allowed_domains", mode="before")
    def _split_domains(cls, value):  # noqa: D401
        """Allow comma-separated strings to define the allowed domains."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("tmp_dir", mode="before")
    def _as_path(cls, value):  # noqa: D401
        """Normalise tmp directory to Path."""
        return Path(value)

    @field_validator("job_ttl_sec")
    def _positive_ttl(cls, value):  # noqa: D401
        """Ensure job TTL is positive."""
        if value <= 0:
            raise ValueError("JOB_TTL_SEC must be greater than zero.")
        return value

    @field_validator("max_file_size_mb")
    def _positive_size(cls, value):  # noqa: D401
        """Ensure max file size limit is positive."""
        if value <= 0:
            raise ValueError("MAX_FILE_SIZE_MB must be greater than zero.")
        return value

    @field_validator("cors_origin")
    def _normalize_cors(cls, value: Optional[str]):  # noqa: D401
        """Normalize empty CORS origin to None."""
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator(
        "rq_job_ttl_sec",
        "rq_result_ttl_sec",
        "rq_failure_ttl_sec",
        "job_ttl_sec",
    )
    def _positive_int(cls, value: int):  # noqa: D401
        if value <= 0:
            raise ValueError("TTL значения должны быть больше нуля.")
        return value

    @field_validator("queue_backend", mode="before")
    def _normalize_backend(cls, value: str):  # noqa: D401
        value = (value or "memory").strip().lower()
        if value not in {"memory", "rq"}:
            raise ValueError("QUEUE_BACKEND должен быть 'memory' или 'rq'.")
        return value

    def ensure_tmp_dir(self) -> Path:
        """Guarantee that the temporary directory exists."""
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        return self.tmp_dir


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""
    settings = Settings()
    settings.ensure_tmp_dir()
    return settings
