"""Configuration for __WORKLOAD_NAME__.

Every value arrives through the environment. Secrets arrive the same way,
injected by the runtime from Secrets Manager, never baked into the image.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"{name} is not set. It is required configuration, not an override.")
    return value


@dataclass(frozen=True)
class Settings:
    workload_name: str = field(default_factory=lambda: _env("WORKLOAD_NAME", "__WORKLOAD_NAME__"))
    environment: str = field(default_factory=lambda: _env("ENVIRONMENT", "local"))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
    port: int = field(default_factory=lambda: int(_env("PORT", "__CONTAINER_PORT__")))
