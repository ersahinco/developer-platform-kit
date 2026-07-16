from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

from churn_prediction_api.model import load_model

ROOT = Path(__file__).resolve().parents[3]
TRAINING_DATA = (
    ROOT / "apps" / "churn_model_train_job" / "sample_data" / "churn_training.csv"
)


def _run_training(output_dir: Path, *, run_id: str) -> dict[str, Any]:
    env = {
        **os.environ,
        "CHURN_TRAINING_DATA_PATH": str(TRAINING_DATA),
        "CHURN_MODEL_OUTPUT_DIR": str(output_dir),
        "CHURN_MODEL_RUN_ID": run_id,
        "CHURN_MODEL_TRAIN_DATE": "2026-05-13",
    }
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


def test_training_emits_lineage_evaluation_and_promotion_evidence(
    tmp_path: Path,
) -> None:
    event = _run_training(tmp_path, run_id="train-run")

    assert event["event"] == "churn_model_train_succeeded"
    assert event["maturity"] == "experimental"
    assert event["pattern"] == "mlops-lineage-and-promotion"
    assert event["model_schema_version"] == 1
    assert event["training_row_count"] == 8
    assert len(event["training_data_sha256"]) == 64
    assert event["evaluation_scope"] == "training-fixture"
    assert event["promotion"]["decision"] == "promote"

    model_path = tmp_path / event["objects"]["model"]
    manifest_path = tmp_path / event["objects"]["manifest"]
    model = load_model(model_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert model["model_version"] == event["model_version"]
    assert model["training_data"]["sha256"] == event["training_data_sha256"]
    assert manifest["model_sha256"] == event["model_sha256"]


def test_training_replay_keeps_model_identity_and_bytes_stable(tmp_path: Path) -> None:
    first = _run_training(tmp_path, run_id="repeatable-train")
    second = _run_training(tmp_path, run_id="repeatable-train")

    assert first["objects"] == second["objects"]
    assert first["model_version"] == second["model_version"]
    assert first["model_sha256"] == second["model_sha256"]
