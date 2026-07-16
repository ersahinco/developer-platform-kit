from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
import json
import threading
from typing import Any, Protocol, cast

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import JSONResponse, Response
import uvicorn

from application.event_processing import (
    record_event_receipt,
    run_event_relay,
)
from application.event_receipts import EventReceiptResult
from application.outbox import OutboxPublisher
from infrastructure.db.event_receipts import SQLAlchemyEventReceiptRepository
from infrastructure.db.outbox import SQLAlchemyOutboxRepository
from infrastructure.db.session import engine_and_session_factory, ping_database
from infrastructure.dapr.pubsub import (
    DaprEventPublisher,
    payload_from_cloud_event,
)
from infrastructure.http_health import (
    database_readiness_response,
    health_payload,
)
from infrastructure.http_observability import request_observability_middleware
from infrastructure.workload_observability import ensure_workload_info_metric
from event_consumer.config import settings


EVENT_CONSUMER_CALLBACK_ROUTE = settings.dapr_subscription_route
WORKLOAD_NAME = "event_consumer"
WORKLOAD_CLASS = "internal-service"

REQUEST_COUNT = Counter(
    "event_consumer_http_requests_total",
    "Event consumer HTTP requests by method, route, and status code.",
    ["method", "route", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "event_consumer_http_request_duration_seconds",
    "Event consumer HTTP request latency by method and route.",
    ["method", "route"],
)
ensure_workload_info_metric(workload=WORKLOAD_NAME, workload_class=WORKLOAD_CLASS)


class StopSignal(Protocol):
    def is_set(self) -> bool: ...

    def wait(self, timeout: float | None = None) -> bool: ...


def consume_event_payload(
    session: Any,
    payload: dict[str, object],
    *,
    now: datetime.datetime | None = None,
) -> EventReceiptResult:
    return record_event_receipt(
        receipts=SQLAlchemyEventReceiptRepository(session),
        payload=payload,
        now=now,
    )


def _engine_and_session_factory() -> tuple[Any, Any]:
    return engine_and_session_factory(str(settings.database_url))


def _publisher() -> DaprEventPublisher:
    return DaprEventPublisher(
        endpoint=settings.dapr_publish_endpoint,
        pubsub_name=settings.dapr_pubsub_name,
        topic=settings.dapr_topic,
    )


def _log_relay_result(result: object) -> None:
    published = getattr(result, "published", 0)
    failed = getattr(result, "failed", 0)
    if published == 0 and failed == 0:
        return
    print(
        json.dumps(
            {
                "workload": WORKLOAD_NAME,
                "event": "outbox_relay",
                "status": "failed" if failed else "succeeded",
                "published": published,
                "failed": failed,
            },
            sort_keys=True,
        ),
        flush=True,
    )


def relay_forever(
    SessionLocal: Any,
    *,
    publisher: OutboxPublisher,
    stop: StopSignal,
) -> None:
    while not stop.is_set():
        with SessionLocal() as session:
            run_event_relay(
                outbox=SQLAlchemyOutboxRepository(session),
                publisher=publisher,
                limit=settings.outbox_relay_batch_size,
                stop_requested=stop.is_set,
                wait_for_retry=stop.wait,
                idle_sleep_seconds=settings.outbox_relay_idle_sleep_seconds,
                run_once=settings.async_event_worker_run_once,
                on_result=_log_relay_result,
            )
        if settings.async_event_worker_run_once:
            return


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine, SessionLocal = _engine_and_session_factory()
    app.state.SessionLocal = SessionLocal
    app.state.relay_stop = threading.Event()
    app.state.relay_thread = None
    if settings.async_event_worker_mode in ("relay", "both"):
        thread = threading.Thread(
            target=relay_forever,
            kwargs={
                "SessionLocal": SessionLocal,
                "publisher": _publisher(),
                "stop": app.state.relay_stop,
            },
            name="event-consumer-outbox-relay",
            daemon=True,
        )
        app.state.relay_thread = thread
        thread.start()
    try:
        yield
    finally:
        app.state.relay_stop.set()
        relay_thread = app.state.relay_thread
        if relay_thread is not None:
            relay_thread.join(timeout=5)
        engine.dispose()


app = FastAPI(title="aws-sdlc-containers-event-consumer", lifespan=lifespan)


def _http_request_event(
    request: Request,
    response: Response,
    request_id: str,
    elapsed_seconds: float,
) -> dict[str, object]:
    return {
        "workload": WORKLOAD_NAME,
        "event": "http_request",
        "event_id": None,
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


@app.get("/dapr/subscribe")
def dapr_subscribe() -> list[dict[str, object]]:
    if settings.async_event_worker_mode not in ("consumer", "both"):
        return []
    return [
        {
            "pubsubname": settings.dapr_pubsub_name,
            "topic": settings.dapr_topic,
            "route": EVENT_CONSUMER_CALLBACK_ROUTE,
        }
    ]


@app.post(EVENT_CONSUMER_CALLBACK_ROUTE)
async def handle_event(request: Request) -> dict[str, str]:
    try:
        body = await request.json()
        payload = payload_from_cloud_event(body)
        with request.app.state.SessionLocal() as session:
            result = consume_event_payload(session, payload)
        print(
            json.dumps(
                {
                    "workload": WORKLOAD_NAME,
                    "event": "event_consumed",
                    "event_id": result.event_id,
                    "request_id": request.state.request_id,
                    "status": result.status,
                },
                sort_keys=True,
            ),
            flush=True,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "workload": WORKLOAD_NAME,
                    "event": "event_consume_failed",
                    "error": str(exc),
                    "request_id": request.state.request_id,
                    "retry": True,
                    "status": "failed",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        raise
    return {"status": "SUCCESS"}


def main() -> None:
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.service_port,
    )


if __name__ == "__main__":
    main()
