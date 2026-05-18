"""API idempotency edge-case and admin write-path tests."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aws_sdlc_containers"
)

from fastapi.testclient import TestClient  # noqa: E402

from api.main import (  # noqa: E402
    app,
    get_config_store,
    get_idempotency_repo,
)


# ---------------------------------------------------------------------------
# Inline stubs
# ---------------------------------------------------------------------------


class _ProcessingIdempotencyRepo:
    """Always reports the key as still processing."""

    def begin(self, *, key: str, request_hash: str) -> object:
        from application.idempotency import IdempotencyBeginResult

        return IdempotencyBeginResult(status="processing")

    def complete(
        self,
        *,
        key: str,
        response_status_code: int,
        response_payload: dict[str, object],
    ) -> None:
        pass

    def fail(self, *, key: str, error: str) -> None:
        pass


class _RecordingConfigStore:
    """Records every set() call; get() always returns None."""

    def __init__(self) -> None:
        self.sets: list[tuple[str, str]] = []

    def get(self, key: str) -> str | None:
        return None

    def set(self, key: str, value: str) -> None:
        self.sets.append((key, value))


# ---------------------------------------------------------------------------
# Override helpers
# ---------------------------------------------------------------------------


def _override_idempotency_repo(repo: object) -> None:
    def get_test_idempotency_repo() -> object:
        return repo

    app.dependency_overrides[get_idempotency_repo] = get_test_idempotency_repo


def _override_config_store(store: object) -> None:
    def get_test_config_store() -> object:
        return store

    app.dependency_overrides[get_config_store] = get_test_config_store


def test_empty_idempotency_key_returns_400() -> None:
    _override_idempotency_repo(_ProcessingIdempotencyRepo())
    try:
        with TestClient(app) as client:
            response = client.post(
                "/orders",
                json={
                    "customer_id": 1,
                    "total_amount": "10.00",
                    "billing_email": "test@example.com",
                },
                headers={"Idempotency-Key": "   "},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_idempotency_key_over_200_chars_returns_400() -> None:
    long_key = "x" * 201
    _override_idempotency_repo(_ProcessingIdempotencyRepo())
    try:
        with TestClient(app) as client:
            response = client.post(
                "/orders",
                json={
                    "customer_id": 1,
                    "total_amount": "10.00",
                    "billing_email": "test@example.com",
                },
                headers={"Idempotency-Key": long_key},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_still_processing_key_returns_409() -> None:
    _override_idempotency_repo(_ProcessingIdempotencyRepo())
    try:
        with TestClient(app) as client:
            response = client.post(
                "/orders",
                json={
                    "customer_id": 1,
                    "total_amount": "10.00",
                    "billing_email": "test@example.com",
                },
                headers={"Idempotency-Key": "test-processing-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "still processing" in response.json()["detail"].lower()


def test_post_write_mode_dual_persists_and_returns_200() -> None:
    config_store = _RecordingConfigStore()
    _override_config_store(config_store)
    try:
        with TestClient(app) as client:
            response = client.post("/admin/write-mode", json={"mode": "dual"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"mode": "dual"}
    assert config_store.sets == [("WRITE_MODE", "dual")]


def test_post_read_mode_new_persists_and_returns_200() -> None:
    config_store = _RecordingConfigStore()
    _override_config_store(config_store)
    try:
        with TestClient(app) as client:
            response = client.post("/admin/read-mode", json={"mode": "new"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"mode": "new"}
    assert config_store.sets == [("READ_MODE", "new")]
