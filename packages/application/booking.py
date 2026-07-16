from __future__ import annotations

import datetime
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from typing import Protocol

from domain.booking import Booking
from domain.booking import BookingSlot


class BookingRepository(Protocol):
    def reserve_if_available(self, booking: Booking) -> bool: ...


@dataclass(frozen=True)
class BookingResult:
    status: Literal["reserved", "conflict"]
    booking: Booking | None


def reserve_slot(
    *,
    resource_id: str,
    starts_at: datetime.datetime,
    customer_id: str,
    repository: BookingRepository,
    booking_id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    now: Callable[[], datetime.datetime] = lambda: datetime.datetime.now(
        tz=datetime.UTC
    ),
) -> BookingResult:
    booking = Booking(
        booking_id=booking_id_factory(),
        slot=BookingSlot(resource_id=resource_id, starts_at=starts_at),
        customer_id=customer_id,
        created_at=now(),
    )
    if repository.reserve_if_available(booking):
        return BookingResult(status="reserved", booking=booking)
    return BookingResult(status="conflict", booking=None)
