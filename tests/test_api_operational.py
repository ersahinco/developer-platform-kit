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

from fastapi.testclient import TestClient  # noqa: E402

from aws_sdlc_api.events import OrderEventPublishError  # noqa: E402
from aws_sdlc_api.main import (  # noqa: E402
    app,
    get_customer_repo,
    get_db,
    get_idempotency_repo,
    get_order_event_publisher,
    get_outbox_repo,
    get_order_repo,
)
from aws_sdlc_api.main import get_config_store  # noqa: E402
from aws_sdlc_core.customer import Customer  # noqa: E402
from aws_sdlc_core.order import Order  # noqa: E402
from aws_sdlc_core.outbox import OutboxMessage  # noqa: E402


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


class _OrderEventPublisher:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.published: list[OutboxMessage] = []

    def publish_order_created(self, order: Order) -> None:
        raise AssertionError("API should dispatch durable outbox messages")

    def publish(self, message: OutboxMessage) -> None:
        if self.should_fail:
            raise OrderEventPublishError("sqs unavailable")
        self.published.append(message)


class _OutboxRepo:
    def __init__(self) -> None:
        self.message = OutboxMessage(
            id=1,
            event_type="order.created.v1",
            event_id="order.created.v1:42",
            aggregate_type="order",
            aggregate_id=42,
            message_group_id="customer-7",
            message_deduplication_id="order.created.v1:42",
            payload={"event_id": "order.created.v1:42"},
            attempt_count=0,
        )
        self.published: list[int] = []
        self.failed: list[dict[str, object]] = []

    def enqueue(self, message: object) -> None:
        raise AssertionError("API order repo owns atomic outbox enqueue")

    def claim_pending(
        self,
        *,
        limit: int,
        now: datetime.datetime,
    ) -> list[OutboxMessage]:
        return [self.message]

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


def _override_order_event_publisher(publisher: object) -> None:
    def get_test_order_event_publisher() -> object:
        return publisher

    app.dependency_overrides[get_order_event_publisher] = get_test_order_event_publisher


def _override_outbox_repo(repo: object) -> None:
    def get_test_outbox_repo() -> object:
        return repo

    app.dependency_overrides[get_outbox_repo] = get_test_outbox_repo


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


def test_create_order_records_outbox_without_inline_dispatch() -> None:
    repo = _OrderRepo()
    outbox = _OutboxRepo()
    publisher = _OrderEventPublisher()
    _override_order_repo(repo)
    _override_customer_repo(_CustomerRepo())
    _override_outbox_repo(outbox)
    _override_order_event_publisher(publisher)
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
    assert publisher.published == []
    assert outbox.published == []


def test_create_order_inline_dispatch_can_be_disabled() -> None:
    outbox = _OutboxRepo()
    _override_order_repo(_OrderRepo())
    _override_customer_repo(_CustomerRepo())
    _override_outbox_repo(outbox)
    _override_order_event_publisher(_OrderEventPublisher(should_fail=True))
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
    assert outbox.published == []
    assert outbox.failed == []


def test_create_order_returns_404_when_customer_is_missing() -> None:
    _override_order_repo(_OrderRepo())
    _override_customer_repo(_CustomerRepo(customer=None))
    _override_order_event_publisher(_OrderEventPublisher())
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
