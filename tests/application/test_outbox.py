from __future__ import annotations

import datetime
from typing import Any

from application.event_processing import run_event_relay
from application.outbox import (
    OutboxMessage,
    dispatch_pending_outbox_messages,
)


_NOW = datetime.datetime(2026, 4, 29, 12, 0, tzinfo=datetime.UTC)


class _OutboxRepo:
    def __init__(self, messages: list[OutboxMessage]) -> None:
        self.messages = messages
        self.published: list[int] = []
        self.failed: list[dict[str, Any]] = []

    def enqueue(self, message: object) -> None:
        raise AssertionError("not used by dispatcher")

    def claim_pending(
        self,
        *,
        limit: int,
        now: datetime.datetime,
    ) -> list[OutboxMessage]:
        return self.messages[:limit]

    def mark_published(
        self,
        *,
        message_id: int,
        now: datetime.datetime,
    ) -> None:
        self.published.append(message_id)

    def mark_failed(
        self,
        *,
        message_id: int,
        error: str,
        next_attempt_at: datetime.datetime,
        now: datetime.datetime,
    ) -> None:
        self.failed.append(
            {
                "message_id": message_id,
                "error": error,
                "next_attempt_at": next_attempt_at,
            }
        )


class _Publisher:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.published: list[OutboxMessage] = []

    def publish(self, message: OutboxMessage) -> None:
        if self.should_fail:
            raise RuntimeError("sqs unavailable")
        self.published.append(message)


def _message(message_id: int = 1) -> OutboxMessage:
    return OutboxMessage(
        id=message_id,
        event_type="order.created.v1",
        event_id=f"order.created.v1:{message_id}",
        aggregate_type="order",
        aggregate_id=message_id,
        message_group_id="customer-7",
        message_deduplication_id=f"order.created.v1:{message_id}",
        payload={"event_id": f"order.created.v1:{message_id}"},
        attempt_count=0,
    )


def test_dispatch_pending_outbox_messages_marks_successful_publish() -> None:
    outbox = _OutboxRepo([_message()])
    publisher = _Publisher()

    result = dispatch_pending_outbox_messages(
        outbox=outbox,
        publisher=publisher,
        limit=10,
        now=_NOW,
    )

    assert result.published == 1
    assert result.failed == 0
    assert [message.id for message in publisher.published] == [1]
    assert outbox.published == [1]
    assert outbox.failed == []


def test_dispatch_pending_outbox_messages_leaves_failed_publish_retryable() -> None:
    outbox = _OutboxRepo([_message()])
    publisher = _Publisher(should_fail=True)

    result = dispatch_pending_outbox_messages(
        outbox=outbox,
        publisher=publisher,
        limit=10,
        now=_NOW,
    )

    assert result.published == 0
    assert result.failed == 1
    assert outbox.published == []
    assert outbox.failed[0]["message_id"] == 1
    assert outbox.failed[0]["error"] == "sqs unavailable"
    assert outbox.failed[0]["next_attempt_at"] > _NOW


def test_event_relay_reports_one_dispatch_and_stops() -> None:
    results = []

    run_event_relay(
        outbox=_OutboxRepo([_message()]),
        publisher=_Publisher(),
        limit=10,
        stop_requested=lambda: False,
        wait_for_retry=lambda _timeout: None,
        idle_sleep_seconds=1.5,
        run_once=True,
        on_result=results.append,
    )

    assert [(result.published, result.failed) for result in results] == [(1, 0)]


def test_event_relay_waits_once_when_idle() -> None:
    stopped = False
    waits: list[float] = []

    def wait_for_retry(timeout: float) -> None:
        nonlocal stopped
        waits.append(timeout)
        stopped = True

    run_event_relay(
        outbox=_OutboxRepo([]),
        publisher=_Publisher(),
        limit=10,
        stop_requested=lambda: stopped,
        wait_for_retry=wait_for_retry,
        idle_sleep_seconds=1.5,
        run_once=False,
    )

    assert waits == [1.5]
