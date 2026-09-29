"""__WORKLOAD_NAME__ lifecycle and platform endpoints."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from app.logging_setup import configure_logging

configure_logging()
logger = logging.getLogger("__WORKLOAD_SLUG__")

REQUESTS = Counter(
    "__WORKLOAD_SLUG___requests_total",
    "Requests handled, by route and outcome.",
    ["route", "outcome"],
)

# Readiness starts after dependency checks and ends at shutdown.
_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _ready
    logger.info("startup", extra={"event": "startup"})
    # Check required dependencies before accepting traffic.
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
