import datetime

from application.operational_snapshot import OperationalSnapshotState
from application.operational_snapshot import build_operational_snapshot


class FakeSnapshotReader:
    def read(self) -> OperationalSnapshotState:
        return OperationalSnapshotState(
            read_mode="new",
            write_mode="dual",
            customers_count=3,
            orders_count=7,
            order_contact_email_count=6,
            outbox_pending_count=2,
            event_receipts_count=5,
        )


def test_build_operational_snapshot_returns_portable_event() -> None:
    captured_at = datetime.datetime(2026, 5, 29, tzinfo=datetime.UTC)

    snapshot = build_operational_snapshot(
        reader=FakeSnapshotReader(),
        run_id="test-run",
        captured_at=captured_at,
    )

    assert snapshot.as_event() == {
        "workload": "operational_snapshot_job",
        "event": "operational_snapshot_succeeded",
        "job_name": "operational_snapshot",
        "run_id": "test-run",
        "mode": "read_only",
        "status": "succeeded",
        "timestamp": captured_at.isoformat(),
        "captured_at": captured_at.isoformat(),
        "read_mode": "new",
        "write_mode": "dual",
        "customers_count": 3,
        "orders_count": 7,
        "order_contact_email_count": 6,
        "outbox_pending_count": 2,
        "event_receipts_count": 5,
    }
