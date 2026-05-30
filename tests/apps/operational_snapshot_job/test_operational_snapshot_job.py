import json

from application.operational_snapshot import OperationalSnapshotState
from operational_snapshot_job.main import run_snapshot


class FakeSnapshotReader:
    def read(self) -> OperationalSnapshotState:
        return OperationalSnapshotState(
            read_mode="new",
            write_mode="new",
            customers_count=1,
            orders_count=2,
            order_contact_email_count=2,
            outbox_pending_count=0,
            event_receipts_count=4,
        )


def test_run_snapshot_emits_structured_success_event(capsys, monkeypatch) -> None:
    monkeypatch.setenv("OPERATIONAL_SNAPSHOT_RUN_ID", "ignored-after-import")

    event = run_snapshot(reader=FakeSnapshotReader())

    assert event["event"] == "operational_snapshot_succeeded"
    assert event["job_name"] == "operational_snapshot"
    assert event["status"] == "succeeded"
    assert event["read_mode"] == "new"
    assert event["orders_count"] == 2

    stdout = capsys.readouterr().out.strip()
    assert json.loads(stdout) == event
