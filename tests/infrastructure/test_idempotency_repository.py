from __future__ import annotations

import datetime
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from infrastructure.db.idempotency import SQLAlchemyIdempotencyRepository
from application.idempotency import IdempotencyBeginResult


def test_new_key_returns_started(committed_db_session) -> None:
    """Req 2.1 — begin with a new key returns started and inserts a processing row."""
    key = uuid.uuid4().hex
    repo = SQLAlchemyIdempotencyRepository(committed_db_session)

    result = repo.begin(key=key, request_hash="hash-abc")

    assert result == IdempotencyBeginResult(status="started")

    row = committed_db_session.execute(
        text("SELECT status FROM idempotency_keys WHERE key=:k"),
        {"k": key},
    ).fetchone()
    assert row is not None
    assert row.status == "processing"


def test_same_key_same_hash_still_processing_returns_processing(
    committed_db_session,
) -> None:
    """Req 2.2 — begin again with same key + same hash while processing returns processing."""
    key = uuid.uuid4().hex
    repo = SQLAlchemyIdempotencyRepository(committed_db_session)

    first = repo.begin(key=key, request_hash="hash-xyz")
    assert first.status == "started"

    second = repo.begin(key=key, request_hash="hash-xyz")

    assert second == IdempotencyBeginResult(status="processing")


def test_begin_after_complete_returns_replay(committed_db_session) -> None:
    """Req 2.3 — begin after complete returns replay with stored payload."""
    key = uuid.uuid4().hex
    repo = SQLAlchemyIdempotencyRepository(committed_db_session)

    repo.begin(key=key, request_hash="hash-replay")
    repo.complete(
        key=key,
        response_status_code=201,
        response_payload={"id": 42, "status": "SUBMITTED"},
    )

    result = repo.begin(key=key, request_hash="hash-replay")

    assert result == IdempotencyBeginResult(
        status="replay",
        response_status_code=201,
        response_payload={"id": 42, "status": "SUBMITTED"},
    )


def test_different_hash_returns_conflict(committed_db_session) -> None:
    """Req 2.4 — begin with same key but different hash returns conflict."""
    key = uuid.uuid4().hex
    repo = SQLAlchemyIdempotencyRepository(committed_db_session)

    repo.begin(key=key, request_hash="hash-original")

    result = repo.begin(key=key, request_hash="hash-different")

    assert result == IdempotencyBeginResult(status="conflict")


def test_complete_persists_payload(committed_db_session) -> None:
    """Req 2.5 — complete updates the row to completed with the supplied payload."""
    key = uuid.uuid4().hex
    repo = SQLAlchemyIdempotencyRepository(committed_db_session)

    repo.begin(key=key, request_hash="hash-complete")
    repo.complete(
        key=key,
        response_status_code=201,
        response_payload={"id": 99},
    )

    row = committed_db_session.execute(
        text(
            "SELECT status, response_status_code, response_payload "
            "FROM idempotency_keys WHERE key=:k"
        ),
        {"k": key},
    ).fetchone()
    assert row is not None
    assert row.status == "completed"
    assert row.response_status_code == 201
    assert row.response_payload == {"id": 99}


def test_fail_persists_error(committed_db_session) -> None:
    """Req 2.6 — fail updates the row to failed and stores the truncated error."""
    key = uuid.uuid4().hex
    repo = SQLAlchemyIdempotencyRepository(committed_db_session)

    repo.begin(key=key, request_hash="hash-fail")
    repo.fail(key=key, error="downstream service unavailable")

    row = committed_db_session.execute(
        text("SELECT status, last_error FROM idempotency_keys WHERE key=:k"),
        {"k": key},
    ).fetchone()
    assert row is not None
    assert row.status == "failed"
    assert row.last_error == "downstream service unavailable"


def test_fail_recovers_from_failed_business_transaction(committed_db_session) -> None:
    key = uuid.uuid4().hex
    repo = SQLAlchemyIdempotencyRepository(committed_db_session)
    repo.begin(key=key, request_hash="hash-failed-transaction")

    with pytest.raises(DBAPIError):
        committed_db_session.execute(text("SELECT * FROM missing_test_table"))

    repo.fail(key=key, error="order write failed")

    row = committed_db_session.execute(
        text("SELECT status, last_error FROM idempotency_keys WHERE key=:k"),
        {"k": key},
    ).fetchone()
    assert row is not None
    assert row.status == "failed"
    assert row.last_error == "order write failed"


def test_expired_processing_lock_resets_and_returns_started(
    committed_db_session,
) -> None:
    """Req 2.7 — begin with an expired processing_expires_at resets the row and returns started."""
    key = uuid.uuid4().hex
    repo = SQLAlchemyIdempotencyRepository(committed_db_session)

    # Insert the row in a processing state with an already-expired lock
    past = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(seconds=120)
    committed_db_session.execute(
        text(
            "INSERT INTO idempotency_keys "
            "(key, request_hash, status, processing_expires_at, created_at, updated_at) "
            "VALUES (:k, :h, 'processing', :exp, NOW(), NOW())"
        ),
        {"k": key, "h": "hash-expired", "exp": past},
    )
    committed_db_session.commit()

    result = repo.begin(key=key, request_hash="hash-expired")

    assert result == IdempotencyBeginResult(status="started")

    row = committed_db_session.execute(
        text("SELECT status FROM idempotency_keys WHERE key=:k"),
        {"k": key},
    ).fetchone()
    assert row is not None
    assert row.status == "processing"
