from __future__ import annotations

import datetime
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "adapters" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "core" / "src"))

from aws_sdlc_adapters.db.repository import SQLAlchemyOutboxRepository  # noqa: E402
from aws_sdlc_core.order_events import OrderEventMessage  # noqa: E402


def _message(event_id: str) -> OrderEventMessage:
    return OrderEventMessage(
        event_type="order.created.v1",
        event_id=event_id,
        aggregate_type="order",
        aggregate_id=999_999_001,
        message_group_id="customer-7",
        message_deduplication_id=event_id,
        payload={"event_id": event_id},
    )


def test_outbox_enqueue_claim_and_mark_published(committed_db_session) -> None:
    repo = SQLAlchemyOutboxRepository(committed_db_session)
    repo.enqueue(_message("order.created.v1:test-published"))
    now = datetime.datetime.now(tz=datetime.UTC)

    messages = repo.claim_pending(limit=10, now=now)

    assert len(messages) == 1
    assert messages[0].event_id == "order.created.v1:test-published"
    assert messages[0].attempt_count == 1

    repo.mark_published(message_id=messages[0].id, now=now)

    status = committed_db_session.execute(
        text("SELECT status FROM outbox_messages WHERE id=:id"),
        {"id": messages[0].id},
    ).scalar_one()
    assert status == "published"


def test_outbox_failed_message_is_retryable(committed_db_session) -> None:
    repo = SQLAlchemyOutboxRepository(committed_db_session)
    repo.enqueue(_message("order.created.v1:test-failed"))
    now = datetime.datetime.now(tz=datetime.UTC)
    retry_at = now + datetime.timedelta(seconds=60)
    message = repo.claim_pending(limit=1, now=now)[0]

    repo.mark_failed(
        message_id=message.id,
        error="sqs unavailable",
        next_attempt_at=retry_at,
        now=now,
    )

    row = committed_db_session.execute(
        text(
            "SELECT status, last_error, next_attempt_at "
            "FROM outbox_messages WHERE id=:id"
        ),
        {"id": message.id},
    ).one()
    assert row.status == "pending"
    assert row.last_error == "sqs unavailable"
    assert row.next_attempt_at == retry_at
