import datetime
from dataclasses import dataclass
from typing import Any, Literal, Protocol

OrderEventReceiptStatus = Literal["processed", "duplicate", "ignored_stale"]


@dataclass(frozen=True)
class OrderEventReceiptResult:
    status: OrderEventReceiptStatus
    event_id: str


class OrderEventReceiptRepository(Protocol):
    def record(
        self, payload: dict[str, Any], *, now: datetime.datetime
    ) -> OrderEventReceiptResult: ...
