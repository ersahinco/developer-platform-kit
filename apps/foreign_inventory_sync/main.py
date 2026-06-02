from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from typing import cast

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import Counter
from prometheus_client import generate_latest
from prometheus_client import Histogram
from starlette.responses import JSONResponse
from starlette.responses import Response
import uvicorn

from foreign_inventory_sync.config import settings
from infrastructure.db.session import engine_and_session_factory
from infrastructure.db.session import ping_database
from infrastructure.http_health import database_readiness_response
from infrastructure.http_health import health_payload
from infrastructure.http_observability import request_observability_middleware
from infrastructure.workload_observability import ensure_workload_info_metric


WORKLOAD_NAME = "foreign_inventory_sync"
WORKLOAD_CLASS = "internal-service"

REQUEST_COUNT = Counter(
    "foreign_inventory_sync_http_requests_total",
    "Foreign inventory sync HTTP requests by method, route, and status code.",
    ["method", "route", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "foreign_inventory_sync_http_request_duration_seconds",
    "Foreign inventory sync HTTP request latency by method and route.",
    ["method", "route"],
)
ensure_workload_info_metric(workload=WORKLOAD_NAME, workload_class=WORKLOAD_CLASS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine, SessionLocal = engine_and_session_factory(str(settings.database_url))
    app.state.SessionLocal = SessionLocal
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="foreign-inventory-sync", lifespan=lifespan)


def _http_request_event(
    request: Request,
    response: Response,
    request_id: str,
    elapsed_seconds: float,
) -> dict[str, object]:
    return {
        "workload": WORKLOAD_NAME,
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "route": getattr(request.scope.get("route"), "path", request.url.path),
        "status": "succeeded" if response.status_code < 500 else "failed",
        "status_code": response.status_code,
        "duration_ms": round(elapsed_seconds * 1000, 3),
    }


app.middleware("http")(
    request_observability_middleware(
        request_count=REQUEST_COUNT,
        request_latency=REQUEST_LATENCY,
        event_payload=_http_request_event,
    )
)


@app.get("/health")
def health() -> dict[str, str]:
    return health_payload()


@app.get("/ready", response_model=None)
def ready(request: Request) -> dict[str, object] | JSONResponse:
    result = database_readiness_response(
        lambda: _ping_session_local(request.app.state.SessionLocal)
    )
    if isinstance(result, JSONResponse):
        return result
    return cast(dict[str, object], result)


def _ping_session_local(session_factory: Any) -> None:
    with session_factory() as session:
        ping_database(session)


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)


if __name__ == "__main__":
    main()
