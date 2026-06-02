from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def _training_data_path() -> str:
    return str(
        ROOT / "apps" / "churn_model_train_job" / "sample_data" / "churn_training.csv"
    )


def _run_training(
    output_dir: Path,
    *,
    run_id: str,
    train_date: str,
) -> dict[str, Any]:
    env = {**os.environ}
    env["CHURN_TRAINING_DATA_PATH"] = _training_data_path()
    env["CHURN_MODEL_OUTPUT_DIR"] = str(output_dir)
    env["CHURN_MODEL_RUN_ID"] = run_id
    env["CHURN_MODEL_TRAIN_DATE"] = train_date
    result = subprocess.run(
        [
            "uv",
            "run",
            "--package",
            "aws-sdlc-containers-churn-model-train-job",
            "python",
            "-m",
            "churn_model_train_job.main",
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


def test_training_writes_model_artifact_manifest_and_evidence(tmp_path: Path) -> None:
    event = _run_training(tmp_path, run_id="train-run", train_date="2026-05-13")

    assert event["event"] == "churn_model_train_succeeded"
    assert event["workload"] == "churn_model_train_job"
    assert event["run_id"] == "train-run"
    assert event["status"] == "succeeded"
    assert event["training_row_count"] == 8
    assert event["model_version"]
    assert event["metrics"]["accuracy"] >= 0.5
    assert event["drift_summary"]["status"] in {"ok", "warning"}

    model_path = tmp_path / event["objects"]["model"]
    manifest_path = tmp_path / event["objects"]["manifest"]
    assert model_path.is_file()
    assert manifest_path.is_file()

    model = json.loads(model_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert model["model_version"] == event["model_version"]
    assert model["run_id"] == "train-run"
    assert manifest["model_sha256"] == event["model_sha256"]
    assert manifest["evidence_paths"] == [
        event["objects"]["model"],
        event["objects"]["manifest"],
    ]
    assert set(model["weights"]) == set(model["features"])


def test_training_is_idempotent_for_same_run_id(tmp_path: Path) -> None:
    first = _run_training(tmp_path, run_id="repeatable-train", train_date="2026-05-13")
    second = _run_training(
        tmp_path,
        run_id="repeatable-train",
        train_date="2026-05-13",
    )

    assert first["objects"] == second["objects"]
    assert first["model_version"] == second["model_version"]
    assert first["training_row_count"] == second["training_row_count"] == 8
