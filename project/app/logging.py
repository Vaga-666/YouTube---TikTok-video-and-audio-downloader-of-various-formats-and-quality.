"""Application-wide logging configuration."""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info:
            data["stack"] = self.formatStack(record.stack_info)

        for attr in ("job_id", "url", "status", "reason"):
            if hasattr(record, attr):
                data[attr] = getattr(record, attr)

        return json.dumps(data, ensure_ascii=False)


def setup_logging() -> logging.Logger:
    """Configure root logger with JSON formatter."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]

    # Silence noisy dependencies at default level
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    return root
