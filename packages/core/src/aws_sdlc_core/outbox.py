import datetime
from dataclasses import dataclass
from typing import Any, Protocol

from aws_sdlc_core.order_events import OrderEventMessage

OUTBOX_FAILURE_BACKOFF_SECONDS = 60


@dataclass(frozen=True)
class OutboxMessage:
    id: int
    event_type: str
    event_id: str
    aggregate_type: str
    aggregate_id: int
    message_group_id: str
    message_deduplication_id: str
    payload: dict[str, Any]
    attempt_count: int


class OutboxRepository(Protocol):
    def enqueue(self, message: OrderEventMessage) -> None: ...

    def claim_pending(
        self,
        *,
        limit: int,
        now: datetime.datetime,
    ) -> list[OutboxMessage]: ...

    def mark_published(
        self,
        *,
        message_id: int,
        now: datetime.datetime,
    ) -> None: ...

    def mark_failed(
        self,
        *,
        message_id: int,
        error: str,
        next_attempt_at: datetime.datetime,
        now: datetime.datetime,
    ) -> None: ...


class OutboxPublisher(Protocol):
    def publish(self, message: OutboxMessage) -> None: ...


@dataclass(frozen=True)
class OutboxDispatchResult:
    published: int
    failed: int


def dispatch_pending_outbox_messages(
    *,
    outbox: OutboxRepository,
    publisher: OutboxPublisher,
    limit: int,
    now: datetime.datetime | None = None,
) -> OutboxDispatchResult:
    if limit <= 0:
        return OutboxDispatchResult(published=0, failed=0)

    started_at = now or datetime.datetime.now(tz=datetime.UTC)
    published = 0
    failed = 0

    for message in outbox.claim_pending(limit=limit, now=started_at):
        try:
            publisher.publish(message)
        except Exception as exc:
            failed += 1
            outbox.mark_failed(
                message_id=message.id,
                error=str(exc),
                next_attempt_at=started_at
                + datetime.timedelta(seconds=OUTBOX_FAILURE_BACKOFF_SECONDS),
                now=started_at,
            )
        else:
            published += 1
            outbox.mark_published(message_id=message.id, now=started_at)

    return OutboxDispatchResult(published=published, failed=failed)
