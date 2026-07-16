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
SOURCE_DIR = ROOT / "apps" / "lake_orders_ingest_job" / "sample_data"
MODEL_PATH = (
    ROOT / "apps" / "lake_orders_ingest_job" / "models" / "curated_lake_orders.sql"
)


def _run_ingest(output_dir: Path, *, run_id: str) -> dict[str, Any]:
    env = {
        **os.environ,
        "LAKE_ORDERS_SOURCE_DIR": str(SOURCE_DIR),
        "LAKE_ORDERS_OUTPUT_DIR": str(output_dir),
        "LAKE_ORDERS_RUN_ID": run_id,
        "LAKE_ORDERS_INGEST_DATE": "2026-05-13",
    }
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


def test_ingest_rebuilds_projection_with_late_and_duplicate_evidence(
    tmp_path: Path,
) -> None:
    event = _run_ingest(tmp_path, run_id="test-run")

    assert event["event"] == "lake_orders_ingest_succeeded"
    assert event["input_row_count"] == 5
    assert event["row_count"] == 4
    assert event["deduplicated_record_count"] == 1
    assert event["late_arrival_count"] == 1
    assert len(event["source_files"]) == 2

    curated_path = tmp_path / event["objects"]["curated"]
    manifest_path = tmp_path / event["objects"]["manifest"]
    assert manifest_path.is_file()

    connection = duckdb.connect(":memory:")
    try:
        updated = connection.execute(
            """
            SELECT status, customer_order_sequence, is_late_arrival
            FROM read_parquet(?) WHERE order_id = '1002'
            """,
            [str(curated_path)],
        ).fetchone()
    finally:
        connection.close()

    assert updated == ("DELIVERED", 1, True)
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == {
        key: value
        for key, value in event.items()
        if key not in {"event", "job_name", "timestamp", "workload"}
    }


def test_ingest_is_idempotent_for_same_run_id(tmp_path: Path) -> None:
    first = _run_ingest(tmp_path, run_id="repeatable-run")
    second = _run_ingest(tmp_path, run_id="repeatable-run")

    assert first["objects"] == second["objects"]
    assert first["raw_sha256"] == second["raw_sha256"]
    assert first["curated_sha256"] == second["curated_sha256"]


def test_failed_replay_removes_stale_success_manifest(tmp_path: Path) -> None:
    model_path = tmp_path / "invalid.sql"
    model_path.write_text("SELECT FROM", encoding="utf-8")
    request = LakeOrdersIngestRequest(
        source_dir=SOURCE_DIR,
        output_dir=tmp_path,
        ingest_date="2026-05-13",
        run_id="invalid-model",
        ingested_at=datetime.datetime(2026, 5, 13, tzinfo=datetime.UTC),
    )
    manifest_path = tmp_path / "manifests/lake_orders/dt=2026-05-13/invalid-model.json"

    run_lake_orders_ingest(request=request, model_path=MODEL_PATH)
    assert manifest_path.is_file()

    with pytest.raises(duckdb.Error):
        run_lake_orders_ingest(request=request, model_path=model_path)

    assert not manifest_path.exists()


def test_ingest_rejects_path_shaped_run_id(tmp_path: Path) -> None:
    request = LakeOrdersIngestRequest(
        source_dir=SOURCE_DIR,
        output_dir=tmp_path,
        ingest_date="2026-05-13",
        run_id="../escape",
        ingested_at=datetime.datetime(2026, 5, 13, tzinfo=datetime.UTC),
    )

    with pytest.raises(ValueError, match="safe"):
        run_lake_orders_ingest(request=request, model_path=MODEL_PATH)
