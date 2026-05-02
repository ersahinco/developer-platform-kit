from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from aws_sdlc_order_event_consumer.main import consume_order_events_once  # noqa: E402


class _SqsClient:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = messages
        self.deleted: list[str] = []

    def receive_message(self, **kwargs: object) -> dict[str, Any]:
        return {"Messages": self.messages}

    def send_message(self, **kwargs: object) -> object:
        return {}

    def delete_message(self, *, QueueUrl: str, ReceiptHandle: str) -> object:
        self.deleted.append(ReceiptHandle)
        return {}


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


def _message(payload: object, receipt_handle: str = "receipt-1") -> dict[str, object]:
    return {"Body": json.dumps(payload), "ReceiptHandle": receipt_handle}


def test_consumer_records_first_delivery_and_deletes_message(committed_db_session):
    payload = _payload("order.created.v1:consumer-first")
    client = _SqsClient([_message(payload)])

    processed = consume_order_events_once(
        committed_db_session,
        queue_url="queue",
        client=client,
        max_messages=10,
        wait_seconds=0,
        visibility_timeout_seconds=30,
    )

    row = committed_db_session.execute(
        text(
            "SELECT status, duplicate_count FROM order_event_receipts WHERE event_id=:id"
        ),
        {"id": payload["event_id"]},
    ).one()
    assert processed == 1
    assert row.status == "processed"
    assert row.duplicate_count == 0
    assert client.deleted == ["receipt-1"]


def test_consumer_deduplicates_repeated_delivery(committed_db_session):
    payload = _payload("order.created.v1:consumer-duplicate")

    for receipt in ("receipt-1", "receipt-2"):
        consume_order_events_once(
            committed_db_session,
            queue_url="queue",
            client=_SqsClient([_message(payload, receipt)]),
            max_messages=10,
            wait_seconds=0,
            visibility_timeout_seconds=30,
        )

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

    consume_order_events_once(
        committed_db_session,
        queue_url="queue",
        client=_SqsClient([_message(newer, "newer")]),
        max_messages=10,
        wait_seconds=0,
        visibility_timeout_seconds=30,
    )
    client = _SqsClient([_message(older, "older")])
    consume_order_events_once(
        committed_db_session,
        queue_url="queue",
        client=client,
        max_messages=10,
        wait_seconds=0,
        visibility_timeout_seconds=30,
    )

    row = committed_db_session.execute(
        text("SELECT status FROM order_event_receipts WHERE event_id=:id"),
        {"id": older["event_id"]},
    ).one()
    assert row.status == "ignored_stale"
    assert client.deleted == ["older"]


def test_consumer_leaves_malformed_message_for_redrive(committed_db_session):
    client = _SqsClient([{"Body": "not-json", "ReceiptHandle": "bad"}])

    processed = consume_order_events_once(
        committed_db_session,
        queue_url="queue",
        client=client,
        max_messages=10,
        wait_seconds=0,
        visibility_timeout_seconds=30,
    )

    assert processed == 0
    assert client.deleted == []
