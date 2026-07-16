from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from domain.booking import Booking
from infrastructure.db.models import BookingModel


class SQLAlchemyBookingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def reserve_if_available(self, booking: Booking) -> bool:
        try:
            result = self._session.execute(
                pg_insert(BookingModel)
                .values(
                    booking_id=booking.booking_id,
                    resource_id=booking.slot.resource_id,
                    starts_at=booking.slot.starts_at,
                    customer_id=booking.customer_id,
                    created_at=booking.created_at,
                )
                .on_conflict_do_nothing(
                    constraint="uq_booking_reservations_resource_slot"
                )
                .returning(BookingModel.booking_id)
            ).scalar_one_or_none()
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return result is not None
