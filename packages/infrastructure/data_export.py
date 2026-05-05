import csv
import datetime
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping

from sqlalchemy import create_engine, text

from application.data_export import ExportedObject

EXPORT_SQL = """
SELECT
  order_id,
  billing_email,
  source,
  updated_at
FROM order_contact_email
ORDER BY order_id
"""


class SQLAlchemyOrderContactEmailExportReader:
    def __init__(self, *, database_url: str) -> None:
        self._database_url = database_url

    def rows(self) -> Iterable[Mapping[str, Any]]:
        engine = create_engine(
            self._database_url,
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
                for row in rows:
                    yield dict(row)
        finally:
            engine.dispose()


class LocalDataExportStore:
    def __init__(self, *, output_dir: str | Path) -> None:
        self._output_dir = Path(output_dir)

    def write_csv(
        self,
        *,
        key: str,
        fieldnames: list[str],
        rows: Iterable[Mapping[str, Any]],
    ) -> ExportedObject:
        path = self._output_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        row_count = 0
        with tmp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _serialize(row.get(key)) for key in fieldnames})
                row_count += 1
        os.replace(tmp_path, path)
        return ExportedObject(
            key=key,
            byte_count=path.stat().st_size,
            sha256=_file_sha256(path),
            row_count=row_count,
            local_path=str(path),
        )

    def write_json(self, *, key: str, payload: Mapping[str, Any]) -> ExportedObject:
        path = self._output_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, path)
        return ExportedObject(
            key=key,
            byte_count=path.stat().st_size,
            sha256=_file_sha256(path),
            local_path=str(path),
        )


class S3DataExportPublisher:
    def __init__(self, *, bucket: str, s3_client: Any | None = None) -> None:
        self._bucket = bucket
        self._s3_client = s3_client

    def publish(self, objects: list[ExportedObject]) -> None:
        client = self._s3_client or _s3_client()
        for item in objects:
            if item.local_path is None:
                raise ValueError(f"export object has no local path: {item.key}")
            _upload_s3_object(
                Path(item.local_path),
                bucket=self._bucket,
                key=item.key,
                s3_client=client,
            )


def publish_s3_outputs(
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


def _serialize(value: Any) -> str | int | float | None:
    if value is None:
        return None
    if isinstance(value, datetime.datetime | datetime.date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
