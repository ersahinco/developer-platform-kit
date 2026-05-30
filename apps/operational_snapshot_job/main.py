import datetime
import json

from application.operational_snapshot import OperationalSnapshotReader
from application.operational_snapshot import build_operational_snapshot
from infrastructure.operational_snapshot import SQLAlchemyOperationalSnapshotReader
from operational_snapshot_job.config import settings


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def run_snapshot(
    reader: OperationalSnapshotReader | None = None,
) -> dict[str, str | int]:
    captured_at = _utc_now()
    snapshot = build_operational_snapshot(
        reader=reader
        or SQLAlchemyOperationalSnapshotReader(
            database_url=settings.required_database_url
        ),
        run_id=settings.operational_snapshot_run_id
        or captured_at.strftime("%Y%m%dT%H%M%SZ"),
        captured_at=captured_at,
    )
    event = snapshot.as_event()
    print(json.dumps(event, sort_keys=True), flush=True)
    return event


def main() -> None:
    run_snapshot()


if __name__ == "__main__":
    main()
