from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from application.outbox import OutboxDispatchResult  # noqa: E402
from application.outbox import OutboxMessage  # noqa: E402
from infrastructure.dapr import pubsub as dapr_pubsub  # noqa: E402
from infrastructure.dapr.pubsub import DaprOrderEventPublisher  # noqa: E402
from order_event_consumer.config import settings  # noqa: E402
from order_event_consumer import main as consumer_main  # noqa: E402
from order_event_consumer.main import app  # noqa: E402
from order_event_consumer.main import consume_order_event_payload  # noqa: E402
from order_event_consumer.main import relay_outbox_once  # noqa: E402


class _Publisher:
    def publish(self, message: object) -> None:
        return None


class _SessionContext:
    def __init__(self, session: object) -> None:
        self._session = session

    def __enter__(self) -> object:
        return self._session

    def __exit__(self, *exc: object) -> None:
        return None


class _Engine:
    def dispose(self) -> None:
        return None


class _ReadySession:
    def execute(self, statement: object) -> None:
        return None


class _FailingSession:
    def execute(self, statement: object) -> None:
        raise RuntimeError("database unavailable")


def _set_lifespan_session(monkeypatch, session: object) -> None:
    monkeypatch.setattr(settings, "order_events_worker_mode", "consumer")
    monkeypatch.setattr(
        consumer_main,
        "_engine_and_session_factory",
        lambda: (_Engine(), lambda: _SessionContext(session)),
    )


def _payload(
    event_id: str,
    *,
    order_id: int = 999_998_001,
    occurred_at: str = "2026-04-29T12:30:00Z",
) -> dict[str, object]:
    return {
        "event_type": "order.created.v1",
        "event_version": 1,
        "event_id": event_id,
        "idempotency_key": event_id,
        "occurred_at": occurred_at,
        "order": {
            "id": order_id,
            "customer_id": 1,
            "total_amount": "10.00",
            "status": "SUBMITTED",
            "submitted_at": occurred_at,
            "created_at": occurred_at,
        },
    }


def _cloud_event(payload: object) -> dict[str, object]:
    return {
        "specversion": "1.0",
        "id": "event-id",
        "source": "aws-sdlc-containers/orders",
        "type": "order.created.v1",
        "data": payload,
    }


def _outbox_message() -> OutboxMessage:
    payload = _payload("order.created.v1:publish", order_id=42)
    return OutboxMessage(
        id=1,
        event_type="order.created.v1",
        event_id="order.created.v1:publish",
        aggregate_type="order",
        aggregate_id=42,
        message_group_id="customer-1",
        message_deduplication_id="order.created.v1:publish",
        payload=payload,
        attempt_count=0,
    )


def test_dapr_publisher_posts_cloud_event(monkeypatch):
    calls: list[tuple[Any, float]] = []

    class _Response:
        status = 204

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    def urlopen(req: object, timeout: float) -> _Response:
        calls.append((req, timeout))
        return _Response()

    monkeypatch.setattr(dapr_pubsub.request, "urlopen", urlopen)
    publisher = DaprOrderEventPublisher(
        endpoint="http://localhost:3500/",
        pubsub_name="order-events-pubsub",
        topic="order-created-v1.fifo",
    )

    publisher.publish(_outbox_message())

    req, timeout = calls[0]
    assert timeout == 10.0
    assert req.full_url == (
        "http://localhost:3500/v1.0/publish/order-events-pubsub/order-created-v1.fifo"
    )
    body = req.data.decode()
    event = json.loads(body)
    assert event["specversion"] == "1.0"
    assert event["id"] == "order.created.v1:publish"
    assert event["type"] == "order.created.v1"
    assert event["source"] == "aws-sdlc-containers/orders"
    assert event["data"]["event_id"] == "order.created.v1:publish"


def test_consumer_records_first_delivery(committed_db_session):
    payload = _payload("order.created.v1:consumer-first")

    result = consume_order_event_payload(
        committed_db_session,
        payload,
    )

    row = committed_db_session.execute(
        text(
            "SELECT status, duplicate_count FROM order_event_receipts WHERE event_id=:id"
        ),
        {"id": payload["event_id"]},
    ).one()
    assert result.status == "processed"
    assert row.status == "processed"
    assert row.duplicate_count == 0


def test_relay_outbox_suppresses_empty_result_log(
    committed_db_session, monkeypatch, capsys
):
    def dispatch_empty(**kwargs: object) -> OutboxDispatchResult:
        return OutboxDispatchResult(published=0, failed=0)

    monkeypatch.setattr(consumer_main, "relay_order_outbox_once", dispatch_empty)

    result = relay_outbox_once(
        committed_db_session,
        publisher=_Publisher(),
        limit=10,
    )

    assert result == 0
    assert capsys.readouterr().out == ""


def test_relay_outbox_logs_non_empty_result(committed_db_session, monkeypatch, capsys):
    def dispatch_published(**kwargs: object) -> OutboxDispatchResult:
        return OutboxDispatchResult(published=1, failed=0)

    monkeypatch.setattr(consumer_main, "relay_order_outbox_once", dispatch_published)

    result = relay_outbox_once(
        committed_db_session,
        publisher=_Publisher(),
        limit=10,
    )

    assert result == 1
    assert json.loads(capsys.readouterr().out) == {
        "event": "outbox_relay",
        "published": 1,
        "failed": 0,
    }


def test_consumer_deduplicates_repeated_delivery(committed_db_session):
    payload = _payload("order.created.v1:consumer-duplicate")

    for _ in range(2):
        consume_order_event_payload(committed_db_session, payload)

    row = committed_db_session.execute(
        text(
            "SELECT status, duplicate_count FROM order_event_receipts WHERE event_id=:id"
        ),
        {"id": payload["event_id"]},
    ).one()
    assert row.status == "processed"
    assert row.duplicate_count == 1


def test_consumer_records_late_stale_event_without_reprocessing(committed_db_session):
    order_id = 999_998_003
    newer = _payload(
        "order.created.v1:consumer-newer",
        order_id=order_id,
        occurred_at="2026-04-29T12:30:00Z",
    )
    older = _payload(
        "order.created.v1:consumer-older",
        order_id=order_id,
        occurred_at="2026-04-29T12:00:00Z",
    )

    consume_order_event_payload(committed_db_session, newer)
    consume_order_event_payload(committed_db_session, older)

    row = committed_db_session.execute(
        text("SELECT status FROM order_event_receipts WHERE event_id=:id"),
        {"id": older["event_id"]},
    ).one()
    assert row.status == "ignored_stale"


def test_consumer_callback_records_delivery(committed_db_session):
    app.state.SessionLocal = lambda: _SessionContext(committed_db_session)
    client = TestClient(app)
    payload = _payload("order.created.v1:callback")

    response = client.post("/internal/events/order-created", json=_cloud_event(payload))

    assert response.status_code == 200
    assert response.json() == {"status": "SUCCESS"}


def test_consumer_callback_logs_request_id(committed_db_session, capsys):
    app.state.SessionLocal = lambda: _SessionContext(committed_db_session)
    client = TestClient(app)
    payload = _payload("order.created.v1:callback-request-id")

    response = client.post(
        "/internal/events/order-created",
        json=_cloud_event(payload),
        headers={"X-Request-ID": "consumer-trace-123"},
    )

    assert response.status_code == 200
    assert json.loads(capsys.readouterr().out) == {
        "event": "order_event_consumed",
        "event_id": "order.created.v1:callback-request-id",
        "request_id": "consumer-trace-123",
        "status": "processed",
    }


def test_consumer_callback_retries_malformed_message(committed_db_session):
    app.state.SessionLocal = lambda: _SessionContext(committed_db_session)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/internal/events/order-created",
        json={"specversion": "1.0", "data": "not-an-object"},
    )

    assert response.status_code == 500


def test_ready_reports_database_ok_when_ping_succeeds(monkeypatch):
    _set_lifespan_session(monkeypatch, _ReadySession())

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


def test_ready_reports_unavailable_when_ping_fails(monkeypatch):
    _set_lifespan_session(monkeypatch, _FailingSession())

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unready",
        "checks": {"database": "unavailable"},
    }


def test_metrics_endpoint_exposes_prometheus_text(monkeypatch):
    _set_lifespan_session(monkeypatch, _ReadySession())

    with TestClient(app) as client:
        health_response = client.get(
            "/health",
            headers={"X-Request-ID": "consumer-health-123"},
        )
        metrics_response = client.get("/metrics")

    assert health_response.status_code == 200
    assert health_response.headers["x-request-id"] == "consumer-health-123"
    assert metrics_response.status_code == 200
    assert "text/plain" in metrics_response.headers["content-type"]
    assert "order_event_consumer_http_requests_total" in metrics_response.text
    assert 'route="/health"' in metrics_response.text


def test_dapr_subscribe_declares_order_topic(monkeypatch):
    monkeypatch.setattr(settings, "order_events_worker_mode", "both")
    monkeypatch.setattr(settings, "order_events_pubsub_name", "order-events-pubsub")
    monkeypatch.setattr(settings, "order_events_topic", "order-created-v1.fifo")

    assert consumer_main.dapr_subscribe() == [
        {
            "pubsubname": "order-events-pubsub",
            "topic": "order-created-v1.fifo",
            "route": "/internal/events/order-created",
        }
    ]
