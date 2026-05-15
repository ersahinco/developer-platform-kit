import datetime
from decimal import Decimal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from domain.order import OrderStatus, ReadModeValue, WriteModeValue

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: int = Field(gt=0)
    total_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    billing_email: str | None = None

    @field_validator("billing_email")
    @classmethod
    def validate_billing_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) > 255 or EMAIL_RE.fullmatch(value) is None:
            raise ValueError("billing_email must be a valid email address")
        return value


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


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


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
