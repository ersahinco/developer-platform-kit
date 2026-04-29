import csv
import datetime
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from config import settings

DATASET = "order_contact_email"
SOURCE_QUERY = "order_contact_email_v1"

EXPORT_SQL = """
SELECT
  order_id,
  billing_email,
  source,
  updated_at
FROM order_contact_email
ORDER BY order_id
"""


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def _serialize(value: Any) -> str | int | float | None:
    if value is None:
        return None
    if isinstance(value, datetime.datetime | datetime.date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True)
        handle.write("\n")
    os.replace(tmp_path, path)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    fieldnames = ["order_id", "billing_email", "source", "updated_at"]
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _serialize(row.get(key)) for key in fieldnames})
    os.replace(tmp_path, path)


def run_export() -> dict[str, Any]:
    exported_at = _utc_now()
    export_date = settings.data_export_date or exported_at.date().isoformat()
    run_id = settings.data_export_run_id or exported_at.strftime("%Y%m%dT%H%M%SZ")

    output_dir = Path(settings.data_export_output_dir)
    raw_dir = output_dir / "raw" / DATASET / f"dt={export_date}"
    manifest_dir = output_dir / "manifests" / DATASET / f"dt={export_date}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / f"{run_id}.csv"
    manifest_path = manifest_dir / f"{run_id}.json"

    engine = create_engine(
        settings.data_export_database_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        with engine.begin() as conn:
            rows = [dict(row) for row in conn.execute(text(EXPORT_SQL)).mappings()]
    finally:
        engine.dispose()

    _write_csv(raw_path, rows)

    manifest = {
        "dataset": DATASET,
        "source_query": SOURCE_QUERY,
        "run_id": run_id,
        "export_date": export_date,
        "exported_at": exported_at.isoformat(),
        "status": "succeeded",
        "row_count": len(rows),
        "objects": {
            "raw": str(raw_path.relative_to(output_dir)),
        },
    }
    _write_json(manifest_path, manifest)
    print(json.dumps(manifest, sort_keys=True), flush=True)
    return manifest


if __name__ == "__main__":
    run_export()
