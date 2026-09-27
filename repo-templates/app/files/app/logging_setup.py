"""Structured JSON logs with stable workload identifiers.

Aggregation only works if every workload can be filtered by the same keys, so
this is wiring rather than a per-team choice.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from app.config import Settings

_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, workload: str, environment: str) -> None:
        super().__init__()
        self._base = {"workload": workload, "environment": environment}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            **self._base,
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(settings.workload_name, settings.environment))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
