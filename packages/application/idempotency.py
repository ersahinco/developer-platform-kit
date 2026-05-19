import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
import time
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


def begin_idempotent_request(
    *,
    idempotency: IdempotencyRepository,
    key: str,
    request_hash: str,
    timeout_seconds: float = 5.0,
    retry_interval_seconds: float = 0.05,
) -> IdempotencyBeginResult:
    deadline = time.monotonic() + timeout_seconds
    while True:
        result = idempotency.begin(key=key, request_hash=request_hash)
        if result.status != "processing" or time.monotonic() >= deadline:
            return result
        time.sleep(retry_interval_seconds)


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
