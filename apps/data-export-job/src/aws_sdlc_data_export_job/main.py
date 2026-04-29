import csv
import datetime
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping

from sqlalchemy import create_engine, text

from aws_sdlc_data_export_job.config import settings

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


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    tmp_path = path.with_name(f"{path.name}.tmp")
    fieldnames = ["order_id", "billing_email", "source", "updated_at"]
    row_count = 0
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _serialize(row.get(key)) for key in fieldnames})
            row_count += 1
    os.replace(tmp_path, path)
    return row_count


def _s3_client() -> Any:
    import boto3

    return boto3.client("s3")


def _upload_s3_object(
    path: Path,
    *,
    bucket: str,
    key: str,
    s3_client: Any,
) -> None:
    with path.open("rb") as handle:
        s3_client.put_object(Bucket=bucket, Key=key, Body=handle)


def _publish_s3_outputs(
    *,
    raw_path: Path,
    manifest_path: Path,
    bucket: str,
    raw_key: str,
    manifest_key: str,
    s3_client: Any,
) -> None:
    _upload_s3_object(raw_path, bucket=bucket, key=raw_key, s3_client=s3_client)
    _upload_s3_object(
        manifest_path,
        bucket=bucket,
        key=manifest_key,
        s3_client=s3_client,
    )


def run_export(s3_client: Any | None = None) -> dict[str, Any]:
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
    raw_key = raw_path.relative_to(output_dir).as_posix()
    manifest_key = manifest_path.relative_to(output_dir).as_posix()

    engine = create_engine(
        settings.data_export_database_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        with engine.begin() as conn:
            rows = (
                conn.execution_options(stream_results=True)
                .execute(text(EXPORT_SQL))
                .mappings()
            )
            row_count = _write_csv(raw_path, rows)
    finally:
        engine.dispose()

    manifest = {
        "dataset": DATASET,
        "source_query": SOURCE_QUERY,
        "run_id": run_id,
        "export_date": export_date,
        "exported_at": exported_at.isoformat(),
        "status": "succeeded",
        "row_count": row_count,
        "objects": {
            "raw": raw_key,
            "manifest": manifest_key,
        },
    }
    _write_json(manifest_path, manifest)

    if settings.data_export_s3_bucket:
        _publish_s3_outputs(
            raw_path=raw_path,
            manifest_path=manifest_path,
            bucket=settings.data_export_s3_bucket,
            raw_key=raw_key,
            manifest_key=manifest_key,
            s3_client=s3_client or _s3_client(),
        )

    print(json.dumps(manifest, sort_keys=True), flush=True)
    return manifest


if __name__ == "__main__":
    run_export()
