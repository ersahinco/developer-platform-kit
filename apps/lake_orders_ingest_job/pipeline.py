from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

DATASET = "lake_orders"
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class LakeOrdersIngestRequest:
    source_dir: Path
    output_dir: Path
    ingest_date: str
    run_id: str
    ingested_at: datetime.datetime


def run_lake_orders_ingest(
    *, request: LakeOrdersIngestRequest, model_path: Path
) -> dict[str, Any]:
    _validate_request(request)
    batch_files = _source_batch_files(request.source_dir)
    keys = _object_keys(request)
    paths = {name: request.output_dir / key for name, key in keys.items()}
    # The manifest is the success marker; a failed replay must not leave it stale.
    paths["manifest"].unlink(missing_ok=True)
    warehouse_path = (
        request.output_dir
        / "_work"
        / DATASET
        / f"dt={request.ingest_date}"
        / request.run_id
        / "warehouse.duckdb"
    )

    raw_stats = _write_raw_parquet(batch_files=batch_files, output_path=paths["raw"])
    _build_model(
        model_path=model_path,
        warehouse_path=warehouse_path,
        raw_parquet_path=paths["raw"],
        ingest_date=request.ingest_date,
    )
    curated_stats = _write_curated_parquet(
        warehouse_path=warehouse_path, output_path=paths["curated"]
    )
    manifest = {
        "contract_version": 1,
        "dataset": DATASET,
        "run_id": request.run_id,
        "ingest_date": request.ingest_date,
        "watermark_date": request.ingest_date,
        "ingested_at": request.ingested_at.isoformat(),
        "status": "succeeded",
        "mode": "run_id",
        "source_files": [
            {"name": path.name, "sha256": _file_sha256(path)} for path in batch_files
        ],
        "input_row_count": raw_stats["row_count"],
        "row_count": curated_stats["row_count"],
        "deduplicated_record_count": raw_stats["row_count"]
        - curated_stats["row_count"],
        "late_arrival_count": curated_stats["late_arrival_count"],
        "raw_sha256": raw_stats["sha256"],
        "curated_sha256": curated_stats["sha256"],
        "model_sha256": _file_sha256(model_path),
        "objects": keys,
        "evidence_paths": [keys["raw"], keys["curated"], keys["manifest"]],
        "artifact_paths": {name: str(path) for name, path in paths.items()},
    }
    _write_json_atomic(paths["manifest"], manifest)
    return manifest


def _validate_request(request: LakeOrdersIngestRequest) -> None:
    if not _RUN_ID.fullmatch(request.run_id):
        raise ValueError("LAKE_ORDERS_RUN_ID must be a safe 1-128 character id")
    try:
        datetime.date.fromisoformat(request.ingest_date)
    except ValueError as exc:
        raise ValueError("LAKE_ORDERS_INGEST_DATE must use YYYY-MM-DD") from exc


def _source_batch_files(source_dir: Path) -> list[Path]:
    if not source_dir.is_dir():
        raise RuntimeError(f"LAKE_ORDERS_SOURCE_DIR is not a directory: {source_dir}")
    paths = sorted(source_dir.glob("*.csv"))
    if not paths:
        raise RuntimeError(f"no lake order batch files found in {source_dir}")
    return paths


def _object_keys(request: LakeOrdersIngestRequest) -> dict[str, str]:
    prefix = f"{DATASET}/dt={request.ingest_date}/{request.run_id}"
    return {
        "raw": f"raw/{prefix}.parquet",
        "curated": f"curated/{prefix}.parquet",
        "manifest": f"manifests/{prefix}.json",
    }


def _write_raw_parquet(*, batch_files: list[Path], output_path: Path) -> dict[str, Any]:
    _ensure_parent(output_path)
    tmp_path = _tmp_path(output_path)
    tmp_path.unlink(missing_ok=True)
    connection = duckdb.connect(":memory:")
    try:
        connection.execute(
            """
            CREATE TABLE incoming_orders AS
            SELECT
              CAST(order_id AS VARCHAR) AS order_id,
              CAST(customer_id AS VARCHAR) AS customer_id,
              CAST(order_ts AS TIMESTAMP) AS order_ts,
              CAST(updated_at AS TIMESTAMP) AS updated_at,
              CAST(status AS VARCHAR) AS status,
              CAST(amount AS DOUBLE) AS amount,
              filename AS source_file
            FROM read_csv_auto(?, HEADER = TRUE, filename = TRUE)
            """,
            [[str(path) for path in batch_files]],
        )
        row = connection.execute("SELECT COUNT(*) FROM incoming_orders").fetchone()
        if row is None:
            raise RuntimeError("DuckDB returned no raw row count")
        connection.execute(
            """
            COPY (
              SELECT * FROM incoming_orders ORDER BY order_id, updated_at, source_file
            ) TO ? (FORMAT PARQUET)
            """,
            [str(tmp_path)],
        )
    finally:
        connection.close()
    os.replace(tmp_path, output_path)
    return {"row_count": int(row[0]), "sha256": _file_sha256(output_path)}


def _build_model(
    *,
    model_path: Path,
    warehouse_path: Path,
    raw_parquet_path: Path,
    ingest_date: str,
) -> None:
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(warehouse_path))
    try:
        connection.execute(
            f"CREATE OR REPLACE TABLE curated_lake_orders AS {model_path.read_text(encoding='utf-8')}",
            [str(raw_parquet_path), ingest_date],
        )
        duplicate = connection.execute(
            """
            SELECT order_id FROM curated_lake_orders
            GROUP BY order_id HAVING COUNT(*) > 1 LIMIT 1
            """
        ).fetchone()
        if duplicate is not None:
            raise ValueError(f"curated order_id is not unique: {duplicate[0]}")
        null_count = connection.execute(
            """
            SELECT COUNT(*) FROM curated_lake_orders
            WHERE order_id IS NULL OR customer_id IS NULL
              OR customer_order_sequence IS NULL
            """
        ).fetchone()
        if null_count is None or int(null_count[0]) != 0:
            raise ValueError("curated orders failed not-null checks")
    finally:
        connection.close()


def _write_curated_parquet(
    *, warehouse_path: Path, output_path: Path
) -> dict[str, Any]:
    _ensure_parent(output_path)
    tmp_path = _tmp_path(output_path)
    tmp_path.unlink(missing_ok=True)
    connection = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        row = connection.execute(
            """
            SELECT COUNT(*), COUNT(*) FILTER (WHERE is_late_arrival)
            FROM curated_lake_orders
            """
        ).fetchone()
        if row is None:
            raise RuntimeError("DuckDB returned no curated row counts")
        connection.execute(
            """
            COPY (SELECT * FROM curated_lake_orders ORDER BY order_id)
            TO ? (FORMAT PARQUET)
            """,
            [str(tmp_path)],
        )
    finally:
        connection.close()
    os.replace(tmp_path, output_path)
    return {
        "row_count": int(row[0]),
        "late_arrival_count": int(row[1]),
        "sha256": _file_sha256(output_path),
    }


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path)
    tmp_path = _tmp_path(path)
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp_path, path)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _tmp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
