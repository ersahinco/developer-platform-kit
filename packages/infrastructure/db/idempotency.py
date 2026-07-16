import datetime
from typing import Any, cast

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from application.idempotency import IdempotencyBeginResult
from infrastructure.db.models import IdempotencyKeyModel

_IDEMPOTENCY_PROCESSING_SECONDS = 60


class SQLAlchemyIdempotencyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def begin(self, *, key: str, request_hash: str) -> IdempotencyBeginResult:
        now = datetime.datetime.now(tz=datetime.UTC)
        processing_expires_at = now + datetime.timedelta(
            seconds=_IDEMPOTENCY_PROCESSING_SECONDS
        )
        result = self._session.execute(
            pg_insert(IdempotencyKeyModel)
            .values(
                key=key,
                request_hash=request_hash,
                status="processing",
                processing_expires_at=processing_expires_at,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["key"])
        )
        self._session.commit()
        if cast(Any, result).rowcount == 1:
            return IdempotencyBeginResult(status="started")

        from sqlalchemy import select as _select  # noqa: PLC0415

        row_data = self._session.execute(
            _select(
                IdempotencyKeyModel.request_hash,
                IdempotencyKeyModel.status,
                IdempotencyKeyModel.processing_expires_at,
                IdempotencyKeyModel.response_status_code,
                IdempotencyKeyModel.response_payload,
            ).where(IdempotencyKeyModel.key == key)
        ).fetchone()
        if row_data is None:
            return IdempotencyBeginResult(status="processing")
        if row_data.request_hash.strip() != request_hash:
            return IdempotencyBeginResult(status="conflict")
        if row_data.status == "completed":
            return IdempotencyBeginResult(
                status="replay",
                response_status_code=row_data.response_status_code,
                response_payload=row_data.response_payload,
            )
        if row_data.processing_expires_at <= now:
            self._session.expire_all()
            row = self._session.get(IdempotencyKeyModel, key)
            if row is not None:
                row.status = "processing"
                row.response_status_code = None
                row.response_payload = None
                row.processing_expires_at = processing_expires_at
                row.last_error = None
                row.updated_at = now
                self._session.commit()
            return IdempotencyBeginResult(status="started")
        return IdempotencyBeginResult(status="processing")

    def complete(
        self,
        *,
        key: str,
        response_status_code: int,
        response_payload: dict[str, object],
    ) -> None:
        row = self._session.get(IdempotencyKeyModel, key)
        if row is None:
            return
        now = datetime.datetime.now(tz=datetime.UTC)
        row.status = "completed"
        row.response_status_code = response_status_code
        row.response_payload = response_payload
        row.last_error = None
        row.updated_at = now
        self._session.commit()

    def fail(self, *, key: str, error: str) -> None:
        self._session.rollback()
        row = self._session.get(IdempotencyKeyModel, key)
        if row is None:
            return
        now = datetime.datetime.now(tz=datetime.UTC)
        row.status = "failed"
        row.last_error = error[:2000]
        row.updated_at = now
        self._session.commit()
