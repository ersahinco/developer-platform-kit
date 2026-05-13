from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
import json
import threading
import time
from typing import Any, Protocol
import uuid

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette import status
from starlette.responses import JSONResponse, Response
import uvicorn

from application.order_event_processing import (
    record_order_event_receipt,
    relay_order_outbox_once,
)
from application.order_event_receipts import OrderEventReceiptResult
from application.outbox import OutboxMessage
from infrastructure.db.repository import (
    SQLAlchemyOrderEventReceiptRepository,
    SQLAlchemyOutboxRepository,
)
from infrastructure.db.session import engine_and_session_factory, ping_database
from infrastructure.dapr.pubsub import (
    DaprOrderEventPublisher,
    payload_from_cloud_event,
)
from order_event_consumer.config import settings


ORDER_EVENTS_CALLBACK_ROUTE = "/internal/events/order-created"

REQUEST_COUNT = Counter(
    "order_event_consumer_http_requests_total",
    "Order event consumer HTTP requests by method, route, and status code.",
    ["method", "route", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "order_event_consumer_http_request_duration_seconds",
    "Order event consumer HTTP request latency by method and route.",
    ["method", "route"],
)


class OrderEventPublisher(Protocol):
    def publish(self, message: OutboxMessage) -> None: ...


def relay_outbox_once(
    session: Any,
    *,
    publisher: OrderEventPublisher,
    limit: int,
) -> int:
    result = relay_order_outbox_once(
        outbox=SQLAlchemyOutboxRepository(session),
        publisher=publisher,
        limit=limit,
    )
    if result.published > 0 or result.failed > 0:
        print(
            json.dumps(
                {
                    "event": "outbox_relay",
                    "published": result.published,
                    "failed": result.failed,
                },
                sort_keys=True,
            ),
            flush=True,
        )
    return result.published + result.failed


def consume_order_event_payload(
    session: Any,
    payload: dict[str, object],
    *,
    now: datetime.datetime | None = None,
) -> OrderEventReceiptResult:
    return record_order_event_receipt(
        receipts=SQLAlchemyOrderEventReceiptRepository(session),
        payload=payload,
        now=now,
    )


def _engine_and_session_factory() -> tuple[Any, Any]:
    return engine_and_session_factory(str(settings.database_url))


def _publisher() -> DaprOrderEventPublisher:
    return DaprOrderEventPublisher(
        endpoint=settings.dapr_publish_endpoint,
        pubsub_name=settings.order_events_pubsub_name,
        topic=settings.order_events_topic,
    )


def relay_forever(
    SessionLocal: Any,
    *,
    publisher: OrderEventPublisher,
    stop: threading.Event,
) -> None:
    while not stop.is_set():
        work_done = 0
        with SessionLocal() as session:
            work_done = relay_outbox_once(
                session,
                publisher=publisher,
                limit=settings.order_events_relay_batch_size,
            )
        if settings.order_events_worker_run_once:
            return
        if work_done == 0:
            stop.wait(settings.order_events_idle_sleep_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine, SessionLocal = _engine_and_session_factory()
    app.state.SessionLocal = SessionLocal
    app.state.relay_stop = threading.Event()
    app.state.relay_thread = None
    if settings.order_events_worker_mode in ("relay", "both"):
        thread = threading.Thread(
            target=relay_forever,
            kwargs={
                "SessionLocal": SessionLocal,
                "publisher": _publisher(),
                "stop": app.state.relay_stop,
            },
            name="order-events-outbox-relay",
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


app = FastAPI(title="aws-sdlc-containers-order-event-consumer", lifespan=lifespan)


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


def _request_id(request: Request) -> str:
    request_id = request.headers.get("x-request-id", "").strip()
    return request_id or uuid.uuid4().hex


@app.middleware("http")
async def observe_requests(request: Request, call_next) -> Response:
    request_id = _request_id(request)
    request.state.request_id = request_id

    if request.url.path == "/metrics":
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        route = _route_label(request)
        REQUEST_COUNT.labels(request.method, route, "500").inc()
        REQUEST_LATENCY.labels(request.method, route).observe(
            time.perf_counter() - started_at
        )
        raise

    route = _route_label(request)
    REQUEST_COUNT.labels(request.method, route, str(response.status_code)).inc()
    elapsed_seconds = time.perf_counter() - started_at
    REQUEST_LATENCY.labels(request.method, route).observe(elapsed_seconds)
    response.headers["X-Request-ID"] = request_id
    print(
        json.dumps(
            {
                "event": "http_request",
                "event_id": None,
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status_code": response.status_code,
                "duration_ms": round(elapsed_seconds * 1000, 3),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", response_model=None)
def ready(request: Request) -> dict[str, object] | JSONResponse:
    try:
        with request.app.state.SessionLocal() as session:
            ping_database(session)
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unready", "checks": {"database": "unavailable"}},
        )

    return {"status": "ready", "checks": {"database": "ok"}}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/dapr/subscribe")
def dapr_subscribe() -> list[dict[str, object]]:
    if settings.order_events_worker_mode not in ("consumer", "both"):
        return []
    return [
        {
            "pubsubname": settings.order_events_pubsub_name,
            "topic": settings.order_events_topic,
            "route": ORDER_EVENTS_CALLBACK_ROUTE,
        }
    ]


@app.post(ORDER_EVENTS_CALLBACK_ROUTE)
async def handle_order_created(request: Request) -> dict[str, str]:
    try:
        body = await request.json()
        payload = payload_from_cloud_event(body)
        with request.app.state.SessionLocal() as session:
            result = consume_order_event_payload(session, payload)
        print(
            json.dumps(
                {
                    "event": "order_event_consumed",
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
                    "event": "order_event_consume_failed",
                    "error": str(exc),
                    "request_id": request.state.request_id,
                    "retry": True,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        raise
    return {"status": "SUCCESS"}


def run_worker(publisher: OrderEventPublisher | None = None) -> None:
    engine, SessionLocal = _engine_and_session_factory()
    stop = threading.Event()
    try:
        relay_forever(SessionLocal, publisher=publisher or _publisher(), stop=stop)
    finally:
        engine.dispose()


def main() -> None:
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.order_events_app_port,
    )


if __name__ == "__main__":
    main()
