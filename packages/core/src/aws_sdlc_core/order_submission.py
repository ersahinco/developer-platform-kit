from decimal import Decimal

from aws_sdlc_core.order import Order
from aws_sdlc_core.ports import CustomerRepository, OrderRepository


class OrderSubmissionError(ValueError):
    pass


class CustomerNotFoundError(OrderSubmissionError):
    pass


class InvalidOrderAmountError(OrderSubmissionError):
    pass


def submit_order(
    *,
    customer_id: int,
    total_amount: Decimal,
    billing_email: str | None,
    customers: CustomerRepository,
    orders: OrderRepository,
) -> Order:
    if total_amount <= Decimal("0"):
        raise InvalidOrderAmountError("total_amount must be greater than zero")

    if customers.get_customer(customer_id) is None:
        raise CustomerNotFoundError(f"Customer {customer_id} not found")

    return orders.create_order(
        customer_id=customer_id,
        total_amount=total_amount,
        billing_email=billing_email,
    )
