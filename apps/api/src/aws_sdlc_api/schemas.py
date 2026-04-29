import datetime
from decimal import Decimal

from pydantic import BaseModel

from aws_sdlc_core.order import OrderStatus, ReadModeValue, WriteModeValue


class CreateOrderRequest(BaseModel):
    customer_id: int
    total_amount: Decimal
    status: OrderStatus
    billing_email: str | None = None


class OrderResponse(BaseModel):
    id: int
    customer_id: int
    total_amount: Decimal
    status: OrderStatus
    submitted_at: datetime.datetime
    created_at: datetime.datetime
    billing_email: str | None = None


class HealthResponse(BaseModel):
    status: str


class CustomerResponse(BaseModel):
    id: int
    name: str
    created_at: datetime.datetime


class ReadModeRequest(BaseModel):
    mode: ReadModeValue


class ReadModeResponse(BaseModel):
    mode: ReadModeValue


class WriteModeRequest(BaseModel):
    mode: WriteModeValue


class WriteModeResponse(BaseModel):
    mode: WriteModeValue
