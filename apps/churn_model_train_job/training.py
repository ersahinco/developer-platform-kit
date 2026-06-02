from __future__ import annotations

import csv
import datetime
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATASET_CHURN_TRAINING = "customer_churn"
MODEL_NAME = "churn_prediction"
FEATURES = [
    "tenure_months",
    "monthly_charges",
    "support_tickets_90d",
    "late_payments_12m",
    "usage_drop_pct",
]
REFERENCE_MEANS = {
    "tenure_months": 20.0,
    "monthly_charges": 78.0,
    "support_tickets_90d": 1.2,
    "late_payments_12m": 0.7,
    "usage_drop_pct": 18.0,
}


@dataclass(frozen=True)
class ChurnTrainingRequest:
    training_data_path: Path
    output_dir: Path
    train_date: str
    run_id: str
    trained_at: datetime.datetime


def train_churn_model(request: ChurnTrainingRequest) -> dict[str, Any]:
    rows = _load_rows(request.training_data_path)
    feature_summary = _feature_summary(rows)
    model = _build_model(rows=rows, feature_summary=feature_summary)
    metrics = _evaluate(rows=rows, model=model)
    drift_summary = _drift_summary(feature_summary)
    model_payload = {
        "model_name": MODEL_NAME,
        "run_id": request.run_id,
        "train_date": request.train_date,
        "trained_at": request.trained_at.isoformat(),
        "features": FEATURES,
        "feature_summary": feature_summary,
        "weights": model["weights"],
        "intercept": model["intercept"],
        "threshold": model["threshold"],
        "metrics": metrics,
        "drift_summary": drift_summary,
    }
    model_version = _model_version(model_payload)
    model_payload["model_version"] = model_version

    keys = _object_keys(request)
    paths = {name: request.output_dir / key for name, key in keys.items()}
    _write_json_atomic(paths["model"], model_payload)
    model_sha256 = _file_sha256(paths["model"])
    manifest = {
        "dataset": DATASET_CHURN_TRAINING,
        "model_name": MODEL_NAME,
        "run_id": request.run_id,
        "model_version": model_version,
        "train_date": request.train_date,
        "trained_at": request.trained_at.isoformat(),
        "status": "succeeded",
        "mode": "run_id",
        "training_row_count": len(rows),
        "feature_summary": feature_summary,
        "metrics": metrics,
        "drift_summary": drift_summary,
        "model_byte_count": paths["model"].stat().st_size,
        "model_sha256": model_sha256,
        "objects": keys,
        "evidence_paths": [keys["model"], keys["manifest"]],
        "artifact_paths": {name: str(path) for name, path in paths.items()},
    }
    _write_json_atomic(paths["manifest"], manifest)
    return manifest


def _load_rows(path: Path) -> list[dict[str, float]]:
    if not path.is_file():
        raise RuntimeError(f"CHURN_TRAINING_DATA_PATH is not a file: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [
            {
                **{feature: float(raw[feature]) for feature in FEATURES},
                "churned": float(raw["churned"]),
            }
            for raw in csv.DictReader(handle)
        ]
    if not rows:
        raise RuntimeError(f"no churn training rows found in {path}")
    return rows


def _feature_summary(rows: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    return {
        feature: {
            "min": min(row[feature] for row in rows),
            "max": max(row[feature] for row in rows),
            "mean": round(_mean(row[feature] for row in rows), 6),
        }
        for feature in FEATURES
    }


def _build_model(
    *,
    rows: list[dict[str, float]],
    feature_summary: dict[str, dict[str, float]],
) -> dict[str, Any]:
    churned_rows = [row for row in rows if row["churned"] == 1.0]
    retained_rows = [row for row in rows if row["churned"] == 0.0]
    base_rate = sum(row["churned"] for row in rows) / len(rows)
    bounded_rate = min(max(base_rate, 0.01), 0.99)
    weights = {}
    for feature in FEATURES:
        span = max(
            feature_summary[feature]["max"] - feature_summary[feature]["min"],
            1.0,
        )
        churn_mean = _mean(row[feature] for row in churned_rows)
        retained_mean = _mean(row[feature] for row in retained_rows)
        weights[feature] = round((churn_mean - retained_mean) / span, 6)
    return {
        "intercept": round(math.log(bounded_rate / (1 - bounded_rate)), 6),
        "weights": weights,
        "threshold": 0.5,
    }


def _evaluate(
    *,
    rows: list[dict[str, float]],
    model: dict[str, Any],
) -> dict[str, float]:
    true_positive = true_negative = false_positive = false_negative = 0
    for row in rows:
        score = _score(row=row, model=model)
        predicted = 1.0 if score >= model["threshold"] else 0.0
        actual = row["churned"]
        if predicted == 1.0 and actual == 1.0:
            true_positive += 1
        elif predicted == 0.0 and actual == 0.0:
            true_negative += 1
        elif predicted == 1.0:
            false_positive += 1
        else:
            false_negative += 1
    total = len(rows)
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    return {
        "accuracy": round((true_positive + true_negative) / total, 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "training_positive_rate": round(
            sum(row["churned"] for row in rows) / total,
            6,
        ),
    }


def _score(*, row: dict[str, float], model: dict[str, Any]) -> float:
    z = float(model["intercept"])
    for feature, weight in model["weights"].items():
        z += float(weight) * float(row[feature])
    return 1 / (1 + math.exp(-z))


def _drift_summary(
    feature_summary: dict[str, dict[str, float]],
) -> dict[str, Any]:
    deltas = {
        feature: round(feature_summary[feature]["mean"] - REFERENCE_MEANS[feature], 6)
        for feature in FEATURES
    }
    max_abs_delta = max(abs(delta) for delta in deltas.values())
    return {
        "reference": "checked_in_baseline_v1",
        "mean_deltas": deltas,
        "max_abs_mean_delta": round(max_abs_delta, 6),
        "status": "warning" if max_abs_delta > 20 else "ok",
    }


def _object_keys(request: ChurnTrainingRequest) -> dict[str, str]:
    prefix = f"{MODEL_NAME}/dt={request.train_date}/{request.run_id}"
    return {
        "model": f"models/{prefix}.json",
        "manifest": f"manifests/{prefix}.json",
    }


def _model_version(payload: dict[str, Any]) -> str:
    stable = {
        key: value
        for key, value in payload.items()
        if key not in {"trained_at", "run_id", "model_version"}
    }
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()
    return digest[:12]


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp_path, path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mean(values: Any) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0
