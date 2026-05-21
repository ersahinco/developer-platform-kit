import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from application.event_receipts import EventReceiptResult
from infrastructure.db.models import EventReceiptModel


def _required_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"event payload must include {key}")
    return value


def _parse_event_time(value: str) -> datetime.datetime:
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.UTC)
    return parsed.astimezone(datetime.UTC)


def _required_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"event payload must include integer {key}")
    return value


class SQLAlchemyEventReceiptRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        payload: dict[str, object],
        *,
        now: datetime.datetime,
    ) -> EventReceiptResult:
        event_id = _required_str(payload, "event_id")
        event_type = _required_str(payload, "event_type")
        idempotency_key = _required_str(payload, "idempotency_key")
        aggregate_type = _required_str(payload, "aggregate_type")
        aggregate_id = _required_int(payload, "aggregate_id")
        occurred_at = _parse_event_time(_required_str(payload, "occurred_at"))

        existing = self._session.get(EventReceiptModel, event_id)
        if existing is not None:
            existing.duplicate_count += 1
            existing.last_seen_at = now
            self._session.commit()
            return EventReceiptResult(status="duplicate", event_id=event_id)

        later_processed = self._session.execute(
            select(EventReceiptModel.event_id)
            .where(
                EventReceiptModel.event_type == event_type,
                EventReceiptModel.aggregate_type == aggregate_type,
                EventReceiptModel.aggregate_id == aggregate_id,
                EventReceiptModel.status == "processed",
                EventReceiptModel.occurred_at > occurred_at,
            )
            .limit(1)
        ).scalar_one_or_none()
        receipt_status = "ignored_stale" if later_processed else "processed"

        self._session.add(
            EventReceiptModel(
                event_id=event_id,
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                idempotency_key=idempotency_key,
                occurred_at=occurred_at,
                payload=payload,
                status=receipt_status,
                duplicate_count=0,
                first_seen_at=now,
                last_seen_at=now,
            )
        )
        self._session.commit()
        return EventReceiptResult(
            status="ignored_stale"
            if receipt_status == "ignored_stale"
            else "processed",
            event_id=event_id,
        )
