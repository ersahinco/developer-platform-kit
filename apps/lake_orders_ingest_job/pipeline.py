from __future__ import annotations

import datetime
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import duckdb

DATASET_LAKE_ORDERS = "lake_orders"


@dataclass(frozen=True)
class LakeOrdersIngestRequest:
    source_dir: Path
    output_dir: Path
    ingest_date: str
    run_id: str
    ingested_at: datetime.datetime


class DbtRunner(Protocol):
    def build(
        self,
        *,
        run_dir: Path,
        warehouse_path: Path,
        raw_parquet_path: Path,
        ingest_date: str,
    ) -> Any: ...


def run_lake_orders_ingest(
    *,
    request: LakeOrdersIngestRequest,
    dbt_runner: DbtRunner,
) -> dict[str, Any]:
    batch_files = _source_batch_files(request.source_dir)
    keys = _object_keys(request)
    paths = {name: request.output_dir / key for name, key in keys.items()}
    run_dir = (
        request.output_dir
        / "_work"
        / DATASET_LAKE_ORDERS
        / f"dt={request.ingest_date}"
        / request.run_id
    )
    warehouse_path = run_dir / "warehouse.duckdb"

    raw_stats = _write_raw_parquet(
        batch_files=batch_files,
        output_path=paths["raw"],
    )
    transform_result = dbt_runner.build(
        run_dir=run_dir,
        warehouse_path=warehouse_path,
        raw_parquet_path=paths["raw"],
        ingest_date=request.ingest_date,
    )
    curated_stats = _write_curated_parquet(
        warehouse_path=warehouse_path,
        output_path=paths["curated"],
    )
    manifest = _success_manifest(
        request=request,
        keys=keys,
        paths=paths,
        batch_files=batch_files,
        raw_stats=raw_stats,
        curated_stats=curated_stats,
        warehouse_path=warehouse_path,
        transform_tool=str(transform_result.transform_tool),
        transform_execution=str(transform_result.transform_execution),
    )
    _write_json_atomic(paths["manifest"], manifest)
    return manifest


def _source_batch_files(source_dir: Path) -> list[Path]:
    if not source_dir.is_dir():
        raise RuntimeError(f"LAKE_ORDERS_SOURCE_DIR is not a directory: {source_dir}")
    batch_files = sorted(source_dir.glob("*.csv"))
    if not batch_files:
        raise RuntimeError(f"no lake order batch files found in {source_dir}")
    return batch_files


def _object_keys(request: LakeOrdersIngestRequest) -> dict[str, str]:
    prefix = f"{DATASET_LAKE_ORDERS}/dt={request.ingest_date}/{request.run_id}"
    return {
        "raw": f"raw/{prefix}.parquet",
        "curated": f"curated/{prefix}.parquet",
        "manifest": f"manifests/{prefix}.json",
    }


def _write_raw_parquet(
    *,
    batch_files: list[Path],
    output_path: Path,
) -> dict[str, Any]:
    _ensure_parent(output_path)
    tmp_path = _tmp_path(output_path)
    _remove_if_exists(tmp_path)
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
            raise RuntimeError("DuckDB count query returned no raw rows")
        row_count = int(row[0])
        connection.execute(
            """
            COPY (
              SELECT *
              FROM incoming_orders
              ORDER BY order_id, updated_at, source_file
            )
            TO ? (FORMAT PARQUET)
            """,
            [str(tmp_path)],
        )
    finally:
        connection.close()
    os.replace(tmp_path, output_path)
    return {
        "row_count": row_count,
        "byte_count": output_path.stat().st_size,
        "sha256": _file_sha256(output_path),
    }


def _write_curated_parquet(
    *,
    warehouse_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    _ensure_parent(output_path)
    tmp_path = _tmp_path(output_path)
    _remove_if_exists(tmp_path)
    connection = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        count_row = connection.execute(
            "SELECT COUNT(*) FROM curated_lake_orders"
        ).fetchone()
        late_row = connection.execute(
            "SELECT COUNT(*) FROM curated_lake_orders WHERE is_late_arrival"
        ).fetchone()
        if count_row is None or late_row is None:
            raise RuntimeError("DuckDB count query returned no curated rows")
        row_count = int(count_row[0])
        late_arrival_count = int(late_row[0])
        connection.execute(
            """
            COPY (
              SELECT *
              FROM curated_lake_orders
              ORDER BY order_id
            )
            TO ? (FORMAT PARQUET)
            """,
            [str(tmp_path)],
        )
    finally:
        connection.close()
    os.replace(tmp_path, output_path)
    return {
        "row_count": row_count,
        "late_arrival_count": late_arrival_count,
        "byte_count": output_path.stat().st_size,
        "sha256": _file_sha256(output_path),
    }


def _success_manifest(
    *,
    request: LakeOrdersIngestRequest,
    keys: dict[str, str],
    paths: dict[str, Path],
    batch_files: list[Path],
    raw_stats: dict[str, Any],
    curated_stats: dict[str, Any],
    warehouse_path: Path,
    transform_tool: str,
    transform_execution: str,
) -> dict[str, Any]:
    evidence_paths = [
        keys["raw"],
        keys["curated"],
        keys["manifest"],
    ]
    return {
        "dataset": DATASET_LAKE_ORDERS,
        "run_id": request.run_id,
        "ingest_date": request.ingest_date,
        "ingested_at": request.ingested_at.isoformat(),
        "status": "succeeded",
        "mode": "run_id",
        "source_file_count": len(batch_files),
        "input_row_count": raw_stats["row_count"],
        "row_count": curated_stats["row_count"],
        "late_arrival_count": curated_stats["late_arrival_count"],
        "parquet_object_count": 2,
        "transform_tool": transform_tool,
        "transform_execution": transform_execution,
        "raw_byte_count": raw_stats["byte_count"],
        "raw_sha256": raw_stats["sha256"],
        "curated_byte_count": curated_stats["byte_count"],
        "curated_sha256": curated_stats["sha256"],
        "objects": keys,
        "evidence_paths": evidence_paths,
        "warehouse_path": str(warehouse_path),
        "artifact_paths": {name: str(path) for name, path in paths.items()},
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


def _remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def _tmp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
