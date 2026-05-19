"""HTTP operational behavior tests that do not require a running server."""

from __future__ import annotations

import os
import datetime
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

os.environ.setdefault(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aws_sdlc_containers"
)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api import telemetry  # noqa: E402
import api.main as api_main  # noqa: E402
from api.main import (  # noqa: E402
    app,
    get_customer_repo,
    get_db,
    get_idempotency_repo,
    get_order_repo,
)
from api.main import get_config_store  # noqa: E402
from api.config import settings  # noqa: E402
from domain.customer import Customer  # noqa: E402
from domain.order import Order  # noqa: E402


class _ReadySession:
    def execute(self, statement: Any) -> None:
        return None


class _FailingSession:
    def execute(self, statement: Any) -> None:
        raise RuntimeError("database unavailable")


class _ConfigStore:
    def __init__(self, values: dict[str, str | None]) -> None:
        self._values = values

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def set(self, key: str, value: str) -> None:
        self._values[key] = value


class _OrderRepo:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []

    def create_order(
        self,
        customer_id: int,
        total_amount: Decimal,
        billing_email: str | None,
    ) -> Order:
        self.created.append(
            {
                "customer_id": customer_id,
                "total_amount": total_amount,
                "billing_email": billing_email,
            }
        )
        now = datetime.datetime(2026, 4, 29, 12, 0, tzinfo=datetime.UTC)
        return Order(
            id=42,
            customer_id=customer_id,
            total_amount=total_amount,
            order_status="SUBMITTED",
            submitted_at=now,
            created_at=now,
            billing_email=billing_email,
        )

    def get_order(self, order_id: int) -> Order | None:
        return None


_DEFAULT_CUSTOMER = Customer(
    id=7,
    name="Test Customer",
    created_at=datetime.datetime(2026, 4, 29, 11, 0, tzinfo=datetime.UTC),
)


class _CustomerRepo:
    def __init__(self, customer: Customer | None = _DEFAULT_CUSTOMER) -> None:
        self.customer = customer

    def get_customer(self, customer_id: int) -> Customer | None:
        if self.customer and self.customer.id == customer_id:
            return self.customer
        return None


class _IdempotencyRepo:
    def begin(self, *, key: str, request_hash: str) -> object:
        raise AssertionError("not used without an Idempotency-Key header")

    def complete(
        self,
        *,
        key: str,
        response_status_code: int,
        response_payload: dict[str, object],
    ) -> None:
        raise AssertionError("not used without an Idempotency-Key header")

    def fail(self, *, key: str, error: str) -> None:
        raise AssertionError("not used without an Idempotency-Key header")


def _override_db(session: object) -> None:
    def get_test_db() -> Iterator[object]:
        yield session

    app.dependency_overrides[get_db] = get_test_db


def _override_config_store(store: object) -> None:
    def get_test_config_store() -> object:
        return store

    app.dependency_overrides[get_config_store] = get_test_config_store


def _override_order_repo(repo: object) -> None:
    def get_test_order_repo() -> object:
        return repo

    app.dependency_overrides[get_order_repo] = get_test_order_repo


def _override_customer_repo(repo: object) -> None:
    def get_test_customer_repo() -> object:
        return repo

    app.dependency_overrides[get_customer_repo] = get_test_customer_repo


def _override_idempotency_repo(repo: object) -> None:
    def get_test_idempotency_repo() -> object:
        return repo

    app.dependency_overrides[get_idempotency_repo] = get_test_idempotency_repo


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


def test_rollout_drill_fault_defaults_to_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rollout_drill_fault_mode", "off")
    _override_db(_ReadySession())
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


def test_rollout_drill_error_fault_returns_configured_status(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rollout_drill_fault_mode", "error")
    monkeypatch.setattr(settings, "rollout_drill_fault_paths", "/ready")
    monkeypatch.setattr(settings, "rollout_drill_fault_status_code", 503)

    with TestClient(app) as client:
        response = client.get("/ready")
        metrics = client.get("/metrics")

    assert response.status_code == 503
    assert response.json() == {"detail": "rollout drill fault injection"}
    assert 'route="/ready",status_code="503"' in metrics.text


def test_rollout_drill_latency_fault_delays_only_configured_paths(
    monkeypatch,
) -> None:
    calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        calls.append(seconds)

    monkeypatch.setattr(settings, "rollout_drill_fault_mode", "latency")
    monkeypatch.setattr(settings, "rollout_drill_fault_paths", "/ready")
    monkeypatch.setattr(settings, "rollout_drill_fault_delay_seconds", 3.0)
    monkeypatch.setattr(api_main.asyncio, "sleep", fake_sleep)
    _override_db(_ReadySession())

    try:
        with TestClient(app) as client:
            health_response = client.get("/health")
            ready_response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert health_response.status_code == 200
    assert ready_response.status_code == 200
    assert calls == [3.0]


def test_rollout_drill_invalid_fault_mode_behaves_as_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rollout_drill_fault_mode", "surprise")
    _override_db(_ReadySession())
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


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


def test_runtime_mode_getters_report_current_config() -> None:
    _override_config_store(_ConfigStore({"READ_MODE": "new", "WRITE_MODE": "dual"}))
    try:
        with TestClient(app) as client:
            read_response = client.get("/admin/read-mode")
            write_response = client.get("/admin/write-mode")
    finally:
        app.dependency_overrides.clear()

    assert read_response.status_code == 200
    assert read_response.json() == {"mode": "new"}
    assert write_response.status_code == 200
    assert write_response.json() == {"mode": "dual"}


def test_runtime_mode_getters_fail_when_config_is_missing() -> None:
    _override_config_store(_ConfigStore({"READ_MODE": None, "WRITE_MODE": None}))
    try:
        with TestClient(app) as client:
            read_response = client.get("/admin/read-mode")
            write_response = client.get("/admin/write-mode")
    finally:
        app.dependency_overrides.clear()

    assert read_response.status_code == 503
    assert write_response.status_code == 503


def test_create_order_uses_application_port_without_inline_dispatch() -> None:
    repo = _OrderRepo()
    _override_order_repo(repo)
    _override_customer_repo(_CustomerRepo())
    _override_idempotency_repo(_IdempotencyRepo())
    try:
        with TestClient(app) as client:
            response = client.post(
                "/orders",
                json={
                    "customer_id": 7,
                    "total_amount": "19.99",
                    "billing_email": "customer@example.com",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["id"] == 42
    assert repo.created == [
        {
            "customer_id": 7,
            "total_amount": Decimal("19.99"),
            "billing_email": "customer@example.com",
        }
    ]


def test_create_order_returns_404_when_customer_is_missing() -> None:
    _override_order_repo(_OrderRepo())
    _override_customer_repo(_CustomerRepo(customer=None))
    try:
        with TestClient(app) as client:
            response = client.post(
                "/orders",
                json={
                    "customer_id": 7,
                    "total_amount": "19.99",
                    "billing_email": "customer@example.com",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Customer 7 not found"


def test_create_order_rejects_client_supplied_status() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/orders",
            json={
                "customer_id": 7,
                "total_amount": "19.99",
                "status": "PAID",
                "billing_email": "customer@example.com",
            },
        )

    assert response.status_code == 422


def test_create_order_rejects_non_positive_amount() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/orders",
            json={
                "customer_id": 7,
                "total_amount": "0.00",
                "billing_email": "customer@example.com",
            },
        )

    assert response.status_code == 422


def test_create_order_rejects_malformed_billing_email() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/orders",
            json={
                "customer_id": 7,
                "total_amount": "19.99",
                "billing_email": "not-an-email",
            },
        )

    assert response.status_code == 422


def test_configure_tracing_excludes_low_value_probe_urls_by_default(
    monkeypatch,
) -> None:
    calls: dict[str, object] = {}

    class _FakeProvider:
        def __init__(self, resource: object) -> None:
            calls["resource"] = resource

        def add_span_processor(self, processor: object) -> None:
            calls["processor"] = processor

    class _FakeExporter:
        def __init__(self, endpoint: str) -> None:
            calls["endpoint"] = endpoint

    class _FakeSpanProcessor:
        def __init__(self, exporter: object) -> None:
            calls["exporter"] = exporter

    class _FakeFastAPIInstrumentor:
        @staticmethod
        def instrument_app(app: FastAPI, **kwargs: object) -> None:
            calls["app"] = app
            calls["fastapi_kwargs"] = kwargs

    class _FakeSQLAlchemyInstrumentor:
        def instrument(self, **kwargs: object) -> None:
            calls["sqlalchemy_kwargs"] = kwargs

    monkeypatch.setenv("OTEL_TRACES_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://tempo/v1/traces")
    monkeypatch.delenv("OTEL_PYTHON_FASTAPI_EXCLUDED_URLS", raising=False)
    monkeypatch.setattr(telemetry, "TracerProvider", _FakeProvider)
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", _FakeExporter)
    monkeypatch.setattr(telemetry, "BatchSpanProcessor", _FakeSpanProcessor)
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", lambda provider: None)
    monkeypatch.setattr(telemetry, "FastAPIInstrumentor", _FakeFastAPIInstrumentor)
    monkeypatch.setattr(
        telemetry, "SQLAlchemyInstrumentor", _FakeSQLAlchemyInstrumentor
    )

    traced_app = FastAPI()
    engine = object()
    telemetry.configure_tracing(app=traced_app, engine=engine)  # type: ignore[arg-type]

    assert calls["endpoint"] == "http://tempo/v1/traces"
    assert calls["app"] is traced_app
    fastapi_kwargs = calls["fastapi_kwargs"]
    assert isinstance(fastapi_kwargs, dict)
    assert fastapi_kwargs["excluded_urls"] == "/health,/metrics"
