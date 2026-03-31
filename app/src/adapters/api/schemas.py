"""
schemas.py — Pydantic request/response models.

Pure data-transfer objects at the HTTP boundary.
No SQLAlchemy or domain imports.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel


class CreateOrderRequest(BaseModel):
    customer_id: int
    total_amount: float
    status: str
    billing_email: str | None = None


class SetReadModeRequest(BaseModel):
    mode: str


class OrderResponse(BaseModel):
    id: int
    customer_id: int
    total_amount: float
    status: str
    submitted_at: datetime.datetime
    created_at: datetime.datetime
    billing_email: str | None = None


class HealthResponse(BaseModel):
    status: str


class SetReadModeResponse(BaseModel):
    read_mode: str
