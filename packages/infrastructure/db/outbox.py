import datetime

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from application.outbox import OutboxMessage
from domain.order_events import OrderEventMessage
from infrastructure.db.models import OutboxMessageModel


def _to_outbox_message(row: OutboxMessageModel) -> OutboxMessage:
    return OutboxMessage(
        id=row.id,
        event_type=row.event_type,
        event_id=row.event_id,
        aggregate_type=row.aggregate_type,
        aggregate_id=row.aggregate_id,
        message_group_id=row.message_group_id,
        message_deduplication_id=row.message_deduplication_id,
        payload=row.payload,
        attempt_count=row.attempt_count,
    )


class SQLAlchemyOutboxRepository:
    _LOCK_SECONDS = 300

    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(self, message: OrderEventMessage) -> None:
        now = datetime.datetime.now(tz=datetime.UTC)
        stmt = (
            pg_insert(OutboxMessageModel)
            .values(
                event_type=message.event_type,
                event_id=message.event_id,
                aggregate_type=message.aggregate_type,
                aggregate_id=message.aggregate_id,
                message_group_id=message.message_group_id,
                message_deduplication_id=message.message_deduplication_id,
                payload=message.payload,
                status="pending",
                attempt_count=0,
                next_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        self._session.execute(stmt)

    def claim_pending(
        self,
        *,
        limit: int,
        now: datetime.datetime,
    ) -> list[OutboxMessage]:
        locked_until = now + datetime.timedelta(seconds=self._LOCK_SECONDS)
        stmt = (
            select(OutboxMessageModel)
            .where(
                OutboxMessageModel.next_attempt_at <= now,
                or_(
                    OutboxMessageModel.status == "pending",
                    (
                        (OutboxMessageModel.status == "processing")
                        & (OutboxMessageModel.locked_until <= now)
                    ),
                ),
            )
            .order_by(OutboxMessageModel.created_at, OutboxMessageModel.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = list(self._session.execute(stmt).scalars())
        for row in rows:
            row.status = "processing"
            row.locked_until = locked_until
            row.attempt_count += 1
            row.updated_at = now
        self._session.commit()
        return [_to_outbox_message(row) for row in rows]

    def mark_published(
        self,
        *,
        message_id: int,
        now: datetime.datetime,
    ) -> None:
        row = self._session.get(OutboxMessageModel, message_id)
        if row is None:
            return
        row.status = "published"
        row.published_at = now
        row.locked_until = None
        row.last_error = None
        row.updated_at = now
        self._session.commit()

    def mark_failed(
        self,
        *,
        message_id: int,
        error: str,
        next_attempt_at: datetime.datetime,
        now: datetime.datetime,
    ) -> None:
        row = self._session.get(OutboxMessageModel, message_id)
        if row is None:
            return
        row.status = "pending"
        row.locked_until = None
        row.last_error = error[:2000]
        row.next_attempt_at = next_attempt_at
        row.updated_at = now
        self._session.commit()
