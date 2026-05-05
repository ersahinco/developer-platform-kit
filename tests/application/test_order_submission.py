from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from domain.customer import Customer
from domain.order import Order
from application.order_submission import (
    CustomerNotFoundError,
    InvalidOrderAmountError,
    submit_order,
)
from application.ports import CustomerRepository, OrderRepository


_NOW = datetime.datetime(2026, 4, 29, 12, 0, tzinfo=datetime.UTC)


class _CustomerRepo(CustomerRepository):
    def __init__(self, customer: Customer | None) -> None:
        self.customer = customer

    def get_customer(self, customer_id: int) -> Customer | None:
        if self.customer and self.customer.id == customer_id:
            return self.customer
        return None


class _OrderRepo(OrderRepository):
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
        return Order(
            id=42,
            customer_id=customer_id,
            total_amount=total_amount,
            order_status="SUBMITTED",
            submitted_at=_NOW,
            created_at=_NOW,
            billing_email=billing_email,
        )

    def get_order(self, order_id: int) -> Order | None:
        return None


def test_submit_order_creates_submitted_order_for_existing_customer() -> None:
    orders = _OrderRepo()
    customer = Customer(id=7, name="Test Customer", created_at=_NOW)

    order = submit_order(
        customer_id=7,
        total_amount=Decimal("19.99"),
        billing_email="customer@example.com",
        customers=_CustomerRepo(customer),
        orders=orders,
    )

    assert order.order_status == "SUBMITTED"
    assert orders.created == [
        {
            "customer_id": 7,
            "total_amount": Decimal("19.99"),
            "billing_email": "customer@example.com",
        }
    ]


def test_submit_order_rejects_missing_customer_without_writing() -> None:
    orders = _OrderRepo()

    with pytest.raises(CustomerNotFoundError, match="Customer 7 not found"):
        submit_order(
            customer_id=7,
            total_amount=Decimal("19.99"),
            billing_email="customer@example.com",
            customers=_CustomerRepo(None),
            orders=orders,
        )

    assert orders.created == []


def test_submit_order_rejects_non_positive_amount_without_writing() -> None:
    orders = _OrderRepo()
    customer = Customer(id=7, name="Test Customer", created_at=_NOW)

    with pytest.raises(InvalidOrderAmountError, match="greater than zero"):
        submit_order(
            customer_id=7,
            total_amount=Decimal("0.00"),
            billing_email="customer@example.com",
            customers=_CustomerRepo(customer),
            orders=orders,
        )

    assert orders.created == []
