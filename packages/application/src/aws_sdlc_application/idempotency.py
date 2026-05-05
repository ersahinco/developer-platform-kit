import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

IdempotencyBeginStatus = Literal["started", "replay", "conflict", "processing"]


@dataclass(frozen=True)
class IdempotencyBeginResult:
    status: IdempotencyBeginStatus
    response_status_code: int | None = None
    response_payload: dict[str, object] | None = None


class IdempotencyRepository(Protocol):
    def begin(self, *, key: str, request_hash: str) -> IdempotencyBeginResult: ...

    def complete(
        self,
        *,
        key: str,
        response_status_code: int,
        response_payload: dict[str, object],
    ) -> None: ...

    def fail(self, *, key: str, error: str) -> None: ...


def order_request_hash(
    *,
    customer_id: int,
    total_amount: Decimal,
    billing_email: str | None,
) -> str:
    payload = {
        "billing_email": billing_email,
        "customer_id": customer_id,
        "total_amount": str(total_amount),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
