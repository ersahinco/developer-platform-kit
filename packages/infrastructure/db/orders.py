import datetime
from decimal import Decimal
from typing import cast

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from application.ports import CustomerRepository, OrderRepository
from domain.customer import Customer
from domain.order import Order, ReadModeValue, WriteModeValue
from domain.order_events import order_created_message
from infrastructure.db.config_store import read_mode_value, write_mode_value
from infrastructure.db.models import CustomerModel, OrderContactEmailModel, OrderModel
from infrastructure.db.outbox import SQLAlchemyOutboxRepository


class SQLAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def _write_mode(self) -> WriteModeValue:
        return cast(WriteModeValue, write_mode_value(self._session))

    def _read_mode(self) -> ReadModeValue:
        return cast(ReadModeValue, read_mode_value(self._session))

    def create_order(
        self,
        customer_id: int,
        total_amount: Decimal,
        billing_email: str | None,
    ) -> Order:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        write_mode = self._write_mode()
        legacy_email = billing_email if write_mode in ("legacy", "dual") else None

        order_row = OrderModel(
            customer_id=customer_id,
            total_amount=total_amount,
            order_status="SUBMITTED",
            submitted_at=now,
            created_at=now,
            billing_email=legacy_email,
        )
        self._session.add(order_row)
        self._session.flush()

        if billing_email is not None and write_mode in ("dual", "new"):
            stmt = (
                pg_insert(OrderContactEmailModel)
                .values(
                    order_id=order_row.id,
                    billing_email=billing_email,
                    source="app",
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["order_id"],
                    set_={
                        "billing_email": billing_email,
                        "source": "app",
                        "updated_at": now,
                    },
                )
            )
            self._session.execute(stmt)

        order = Order(
            id=order_row.id,
            customer_id=order_row.customer_id,
            total_amount=order_row.total_amount,
            order_status=order_row.order_status,
            submitted_at=order_row.submitted_at,
            created_at=order_row.created_at,
            billing_email=billing_email,
        )
        SQLAlchemyOutboxRepository(self._session).enqueue(order_created_message(order))

        self._session.commit()
        self._session.refresh(order_row)

        read_mode = self._read_mode()
        if read_mode == "legacy":
            returned_email = order_row.billing_email
        else:
            contact = self._session.get(OrderContactEmailModel, order_row.id)
            returned_email = contact.billing_email if contact else None

        return Order(
            id=order_row.id,
            customer_id=order_row.customer_id,
            total_amount=order_row.total_amount,
            order_status=order_row.order_status,
            submitted_at=order_row.submitted_at,
            created_at=order_row.created_at,
            billing_email=returned_email,
        )

    def get_order(self, order_id: int) -> Order | None:
        order_row = self._session.get(OrderModel, order_id)
        if order_row is None:
            return None

        read_mode = self._read_mode()
        if read_mode == "legacy":
            billing_email = order_row.billing_email
        else:
            contact = self._session.get(OrderContactEmailModel, order_id)
            billing_email = contact.billing_email if contact else None

        return Order(
            id=order_row.id,
            customer_id=order_row.customer_id,
            total_amount=order_row.total_amount,
            order_status=order_row.order_status,
            submitted_at=order_row.submitted_at,
            created_at=order_row.created_at,
            billing_email=billing_email,
        )


class SQLAlchemyCustomerRepository(CustomerRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_customer(self, customer_id: int) -> Customer | None:
        row = self._session.get(CustomerModel, customer_id)
        if row is None:
            return None
        return Customer(id=row.id, name=row.name, created_at=row.created_at)
