import datetime

import pytest

from application.booking import reserve_slot
from domain.booking import Booking
from domain.booking import BookingSlot


class _Repository:
    def __init__(self, available: bool) -> None:
        self.available = available
        self.booking: Booking | None = None

    def reserve_if_available(self, booking: Booking) -> bool:
        self.booking = booking
        return self.available


def test_reserve_slot_returns_reserved_with_domain_booking() -> None:
    repository = _Repository(available=True)
    starts_at = datetime.datetime(2030, 1, 1, 10, tzinfo=datetime.UTC)
    created_at = datetime.datetime(2026, 7, 16, tzinfo=datetime.UTC)

    result = reserve_slot(
        resource_id="room-1",
        starts_at=starts_at,
        customer_id="customer-1",
        repository=repository,
        booking_id_factory=lambda: "booking-1",
        now=lambda: created_at,
    )

    assert result.status == "reserved"
    assert result.booking == Booking(
        booking_id="booking-1",
        slot=BookingSlot(resource_id="room-1", starts_at=starts_at),
        customer_id="customer-1",
        created_at=created_at,
    )


def test_reserve_slot_returns_conflict_without_leaking_losing_booking() -> None:
    result = reserve_slot(
        resource_id="room-1",
        starts_at=datetime.datetime(2030, 1, 1, 10, tzinfo=datetime.UTC),
        customer_id="customer-2",
        repository=_Repository(available=False),
    )

    assert result.status == "conflict"
    assert result.booking is None


def test_booking_slot_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        BookingSlot(
            resource_id="room-1",
            starts_at=datetime.datetime(2030, 1, 1, 10),
        )
