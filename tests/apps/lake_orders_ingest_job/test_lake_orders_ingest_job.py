from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import duckdb
import pytest

from lake_orders_ingest_job.pipeline import LakeOrdersIngestRequest
from lake_orders_ingest_job.pipeline import run_lake_orders_ingest

ROOT = Path(__file__).resolve().parents[3]


def _sample_source_dir() -> str:
    return str(ROOT / "apps" / "lake_orders_ingest_job" / "sample_data")


def _run_ingest(output_dir: Path, *, run_id: str, ingest_date: str) -> dict[str, Any]:
    env = {**os.environ}
    env["LAKE_ORDERS_SOURCE_DIR"] = _sample_source_dir()
    env["LAKE_ORDERS_OUTPUT_DIR"] = str(output_dir)
    env["LAKE_ORDERS_RUN_ID"] = run_id
    env["LAKE_ORDERS_INGEST_DATE"] = ingest_date
    result = subprocess.run(
        [
            "uv",
            "run",
            "--package",
            "aws-sdlc-containers-lake-orders-ingest-job",
            "python",
            "-m",
            "lake_orders_ingest_job.main",
        ],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    event = json.loads(result.stdout)
    assert isinstance(event, dict)
    return event


def test_run_ingest_writes_parquet_transform_and_manifest(
    tmp_path,
) -> None:
    event = _run_ingest(tmp_path, run_id="test-run", ingest_date="2026-05-13")

    assert event["event"] == "lake_orders_ingest_succeeded"
    assert event["workload"] == "lake_orders_ingest_job"
    assert event["run_id"] == "test-run"
    assert event["status"] == "succeeded"
    assert event["row_count"] == 4
    assert event["late_arrival_count"] == 1
    assert event["parquet_object_count"] == 2
    assert event["evidence_paths"] == [
        event["objects"]["raw"],
        event["objects"]["curated"],
        event["objects"]["manifest"],
    ]

    raw_path = tmp_path / event["objects"]["raw"]
    curated_path = tmp_path / event["objects"]["curated"]
    manifest_path = tmp_path / event["objects"]["manifest"]

    assert raw_path.is_file()
    assert curated_path.is_file()
    assert manifest_path.is_file()

    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert on_disk["status"] == "succeeded"
    assert on_disk["input_row_count"] == 5
    assert on_disk["row_count"] == 4
    assert on_disk["late_arrival_count"] == 1

    connection = duckdb.connect(":memory:")
    try:
        raw_count = connection.execute(
            "SELECT COUNT(*) FROM read_parquet(?)", [str(raw_path)]
        ).fetchone()
        curated_count = connection.execute(
            "SELECT COUNT(*) FROM read_parquet(?)", [str(curated_path)]
        ).fetchone()
        window_row = connection.execute(
            """
            SELECT
              status,
              customer_order_sequence,
              customer_running_amount,
              previous_order_ts,
              is_late_arrival
            FROM read_parquet(?)
            WHERE order_id = '1002'
            """,
            [str(curated_path)],
        ).fetchone()
        following_row = connection.execute(
            """
            SELECT
              customer_order_sequence,
              previous_order_ts
            FROM read_parquet(?)
            WHERE order_id = '1001'
            """,
            [str(curated_path)],
        ).fetchone()
    finally:
        connection.close()

    assert raw_count == (5,)
    assert curated_count == (4,)
    assert window_row is not None
    assert window_row[0] == "DELIVERED"
    assert window_row[1] == 1
    assert window_row[2] == 23.5
    assert window_row[3] is None
    assert window_row[4] is True
    assert following_row is not None
    assert following_row[0] == 2
    assert following_row[1] is not None


def test_run_ingest_is_idempotent_for_same_run_id(tmp_path) -> None:
    first_manifest = _run_ingest(
        tmp_path,
        run_id="repeatable-run",
        ingest_date="2026-05-13",
    )
    second_manifest = _run_ingest(
        tmp_path,
        run_id="repeatable-run",
        ingest_date="2026-05-13",
    )

    assert first_manifest["objects"] == second_manifest["objects"]
    assert first_manifest["row_count"] == second_manifest["row_count"] == 4
    assert (
        first_manifest["late_arrival_count"]
        == second_manifest["late_arrival_count"]
        == 1
    )

    curated_path = tmp_path / second_manifest["objects"]["curated"]
    connection = duckdb.connect(":memory:")
    try:
        row = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT order_id) FROM read_parquet(?)",
            [str(curated_path)],
        ).fetchone()
    finally:
        connection.close()

    assert row == (4, 4)


def test_run_ingest_does_not_write_manifest_when_model_fails(tmp_path) -> None:
    model_path = tmp_path / "invalid.sql"
    model_path.write_text("SELECT FROM", encoding="utf-8")
    request = LakeOrdersIngestRequest(
        source_dir=Path(_sample_source_dir()),
        output_dir=tmp_path,
        ingest_date="2026-05-13",
        run_id="invalid-model",
        ingested_at=datetime.datetime(2026, 5, 13, tzinfo=datetime.UTC),
    )

    with pytest.raises(duckdb.Error):
        run_lake_orders_ingest(request=request, model_path=model_path)

    manifest_path = tmp_path / "manifests/lake_orders/dt=2026-05-13/invalid-model.json"
    assert not manifest_path.exists()
