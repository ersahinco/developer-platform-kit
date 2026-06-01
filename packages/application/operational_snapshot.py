import datetime
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OperationalSnapshotState:
    read_mode: str
    write_mode: str
    customers_count: int
    orders_count: int
    order_contact_email_count: int
    outbox_pending_count: int
    event_receipts_count: int


@dataclass(frozen=True)
class OperationalSnapshot:
    run_id: str
    captured_at: datetime.datetime
    state: OperationalSnapshotState

    def as_event(self) -> dict[str, str | int]:
        return {
            "workload": "operational_snapshot_job",
            "event": "operational_snapshot_succeeded",
            "job_name": "operational_snapshot",
            "run_id": self.run_id,
            "mode": "read_only",
            "status": "succeeded",
            "timestamp": self.captured_at.isoformat(),
            "captured_at": self.captured_at.isoformat(),
            "read_mode": self.state.read_mode,
            "write_mode": self.state.write_mode,
            "customers_count": self.state.customers_count,
            "orders_count": self.state.orders_count,
            "order_contact_email_count": self.state.order_contact_email_count,
            "outbox_pending_count": self.state.outbox_pending_count,
            "event_receipts_count": self.state.event_receipts_count,
        }


class OperationalSnapshotReader(Protocol):
    def read(self) -> OperationalSnapshotState: ...


def build_operational_snapshot(
    *,
    reader: OperationalSnapshotReader,
    run_id: str,
    captured_at: datetime.datetime,
) -> OperationalSnapshot:
    return OperationalSnapshot(
        run_id=run_id,
        captured_at=captured_at,
        state=reader.read(),
    )
