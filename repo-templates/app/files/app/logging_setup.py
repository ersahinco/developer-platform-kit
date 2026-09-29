"""JSON logs with workload identity and runtime environment settings."""

from __future__ import annotations

import json
import logging
import os
import sys

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
        payload = {
            **self._base,
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **{key: value for key, value in vars(record).items() if key not in _RESERVED},
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            os.getenv("WORKLOAD_NAME", "__WORKLOAD_NAME__"),
            os.getenv("ENVIRONMENT", "local"),
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
