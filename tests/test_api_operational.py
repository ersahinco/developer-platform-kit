"""HTTP operational behavior tests that do not require a running server."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

os.environ.setdefault(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aws_sdlc_containers"
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "adapters" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "core" / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from aws_sdlc_api.main import app, get_db  # noqa: E402


class _ReadySession:
    def execute(self, statement: Any) -> None:
        return None


class _FailingSession:
    def execute(self, statement: Any) -> None:
        raise RuntimeError("database unavailable")


def _override_db(session: object) -> None:
    def get_test_db() -> Iterator[object]:
        yield session

    app.dependency_overrides[get_db] = get_test_db


def test_ready_reports_database_ok_when_ping_succeeds() -> None:
    _override_db(_ReadySession())
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


def test_ready_reports_unavailable_when_ping_fails() -> None:
    _override_db(_FailingSession())
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "unready",
        "checks": {"database": "unavailable"},
    }


def test_request_id_header_is_generated_when_absent() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-request-id"]


def test_request_id_header_is_propagated_when_supplied() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "trace-123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "trace-123"
