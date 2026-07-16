import datetime

from fastapi.testclient import TestClient

from booking_api.main import app
from booking_api.main import get_booking_repository
from domain.booking import Booking
from domain.booking import BookingSlot


class _Repository:
    def __init__(self, available: bool) -> None:
        self.available = available

    def reserve_if_available(self, _booking: Booking) -> bool:
        return self.available


def _payload() -> dict[str, str]:
    return {
        "resource_id": "room-1",
        "starts_at": "2030-01-01T10:00:00Z",
        "customer_id": "customer-1",
    }


def test_booking_api_exposes_service_contract_and_reserves() -> None:
    app.dependency_overrides[get_booking_repository] = lambda: _Repository(True)
    try:
        with TestClient(app) as client:
            health = client.get("/health")
            response = client.post("/bookings", json=_payload())
            metrics = client.get("/metrics")
    finally:
        app.dependency_overrides.clear()

    assert health.status_code == 200
    assert response.status_code == 201
    assert response.json()["status"] == "reserved"
    assert metrics.status_code == 200
    assert "booking_attempts_total" in metrics.text


def test_booking_api_reports_slot_conflict() -> None:
    app.dependency_overrides[get_booking_repository] = lambda: _Repository(False)
    try:
        with TestClient(app) as client:
            response = client.post("/bookings", json=_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["status"] == "conflict"


def test_booking_domain_response_preserves_utc_slot() -> None:
    slot = BookingSlot(
        resource_id="room-1",
        starts_at=datetime.datetime(2030, 1, 1, 10, tzinfo=datetime.UTC),
    )
    assert slot.starts_at.utcoffset() == datetime.timedelta(0)
