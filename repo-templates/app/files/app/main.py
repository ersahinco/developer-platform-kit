"""__WORKLOAD_NAME__ host.

Owns process lifecycle, the platform endpoints, logging, and wiring. Business
logic goes in its own modules so it stays testable without a running server.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from app.config import Settings
from app.logging_setup import configure_logging

settings = Settings()
configure_logging(settings)
logger = logging.getLogger("__WORKLOAD_SLUG__")

REQUESTS = Counter(
    "__WORKLOAD_SLUG___requests_total",
    "Requests handled, by route and outcome.",
    ["route", "outcome"],
)

# Liveness and readiness are different questions. The process can be alive and
# unable to serve, and the load balancer must be able to tell them apart.
_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _ready
    logger.info("startup", extra={"event": "startup"})
    # Check dependencies here. Fail loudly rather than serving a broken workload.
    _ready = True
    yield
    _ready = False
    logger.info("shutdown", extra={"event": "shutdown"})


app = FastAPI(title="__WORKLOAD_NAME__", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness. The process is up. Never checks dependencies."""
    REQUESTS.labels(route="/health", outcome="ok").inc()
    return {"status": "ok", "workload": "__WORKLOAD_NAME__"}


@app.get("/ready")
def ready(response: Response) -> dict[str, str]:
    """Readiness. This instance can serve traffic right now."""
    if not _ready:
        response.status_code = 503
        REQUESTS.labels(route="/ready", outcome="not_ready").inc()
        return {"status": "not_ready", "workload": "__WORKLOAD_NAME__"}
    REQUESTS.labels(route="/ready", outcome="ok").inc()
    return {"status": "ready", "workload": "__WORKLOAD_NAME__"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
