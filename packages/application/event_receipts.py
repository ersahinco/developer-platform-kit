import datetime
from dataclasses import dataclass
from typing import Any, Literal, Protocol

EventReceiptStatus = Literal["processed", "duplicate", "ignored_stale"]


@dataclass(frozen=True)
class EventReceiptResult:
    status: EventReceiptStatus
    event_id: str


class EventReceiptRepository(Protocol):
    def record(
        self, payload: dict[str, Any], *, now: datetime.datetime
    ) -> EventReceiptResult: ...
