from __future__ import annotations

import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from domain.booking import Booking
from domain.booking import BookingSlot
from infrastructure.db.bookings import SQLAlchemyBookingRepository


def test_concurrent_booking_attempts_have_one_database_winner(db_engine) -> None:
    resource_id = "concurrency-proof-room"
    starts_at = datetime.datetime(2030, 1, 1, 10, tzinfo=datetime.UTC)
    barrier = threading.Barrier(2)

    def attempt(index: int) -> bool:
        with sessionmaker(db_engine)() as session:
            barrier.wait()
            return SQLAlchemyBookingRepository(session).reserve_if_available(
                Booking(
                    booking_id=f"concurrent-booking-{index}",
                    slot=BookingSlot(resource_id=resource_id, starts_at=starts_at),
                    customer_id=f"customer-{index}",
                    created_at=datetime.datetime.now(tz=datetime.UTC),
                )
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, [1, 2]))

        with db_engine.connect() as connection:
            count = connection.execute(
                text(
                    "SELECT COUNT(*) FROM booking_reservations "
                    "WHERE resource_id=:resource_id AND starts_at=:starts_at"
                ),
                {"resource_id": resource_id, "starts_at": starts_at},
            ).scalar_one()

        assert sorted(results) == [False, True]
        assert count == 1
    finally:
        with db_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM booking_reservations WHERE resource_id=:resource_id"),
                {"resource_id": resource_id},
            )


def test_booking_repository_rolls_back_before_session_reuse(db_session) -> None:
    repository = SQLAlchemyBookingRepository(db_session)
    starts_at = datetime.datetime(2030, 1, 2, 10, tzinfo=datetime.UTC)

    def booking(booking_id: str, resource_id: str) -> Booking:
        return Booking(
            booking_id=booking_id,
            slot=BookingSlot(resource_id=resource_id, starts_at=starts_at),
            customer_id="rollback-proof-customer",
            created_at=datetime.datetime.now(tz=datetime.UTC),
        )

    try:
        assert repository.reserve_if_available(booking("shared-id", "room-a"))
        with pytest.raises(IntegrityError):
            repository.reserve_if_available(booking("shared-id", "room-b"))

        assert repository.reserve_if_available(booking("fresh-id", "room-c"))
    finally:
        db_session.execute(
            text(
                "DELETE FROM booking_reservations "
                "WHERE customer_id='rollback-proof-customer'"
            )
        )
        db_session.commit()
