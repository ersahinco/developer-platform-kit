from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field


class TriageRequest(BaseModel):
    ticket_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    customer_tier: str = "standard"
    run_id: str | None = None


class EvalRequest(BaseModel):
    run_id: str | None = None
