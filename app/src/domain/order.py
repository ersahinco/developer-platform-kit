from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass
class Order:
    id: int
    customer_id: int
    total_amount: float
    status: str
    submitted_at: datetime.datetime
    created_at: datetime.datetime
    billing_email: str | None = None
