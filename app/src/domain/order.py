import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

OrderStatus = Literal["SUBMITTED", "PAID", "CANCELLED"]
ReadModeValue = Literal["legacy", "new"]
WriteModeValue = Literal["legacy", "dual", "new"]


@dataclass
class Order:
    id: int
    customer_id: int
    total_amount: Decimal
    order_status: OrderStatus
    submitted_at: datetime.datetime
    created_at: datetime.datetime
    billing_email: str | None = None
