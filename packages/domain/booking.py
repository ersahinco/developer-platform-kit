from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class BookingSlot:
    resource_id: str
    starts_at: datetime.datetime

    def __post_init__(self) -> None:
        if not self.resource_id.strip():
            raise ValueError("resource_id must not be empty")
        if self.starts_at.tzinfo is None or self.starts_at.utcoffset() is None:
            raise ValueError("starts_at must include a timezone")


@dataclass(frozen=True)
class Booking:
    booking_id: str
    slot: BookingSlot
    customer_id: str
    created_at: datetime.datetime

    def __post_init__(self) -> None:
        if not self.booking_id.strip():
            raise ValueError("booking_id must not be empty")
        if not self.customer_id.strip():
            raise ValueError("customer_id must not be empty")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
