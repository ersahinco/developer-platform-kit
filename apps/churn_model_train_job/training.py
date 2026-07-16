from __future__ import annotations

import csv
import datetime
import hashlib
import json
import math
import os
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATASET = "customer_churn"
MODEL_NAME = "churn_prediction"
MODEL_SCHEMA_VERSION = 1
ALGORITHM = "standardized-mean-difference-v1"
FEATURES = (
    "tenure_months",
    "monthly_charges",
    "support_tickets_90d",
    "late_payments_12m",
    "usage_drop_pct",
)
REFERENCE_MEANS = {
    "tenure_months": 20.0,
    "monthly_charges": 78.0,
    "support_tickets_90d": 1.2,
    "late_payments_12m": 0.7,
    "usage_drop_pct": 18.0,
}
PROMOTION_MIN_ACCURACY = 0.75
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class ChurnTrainingRequest:
    training_data_path: Path
    output_dir: Path
    train_date: str
    run_id: str
    trained_at: datetime.datetime


def train_churn_model(request: ChurnTrainingRequest) -> dict[str, Any]:
    _validate_request(request)
    rows = _load_rows(request.training_data_path)
    summary = _feature_summary(rows)
    model = _build_model(rows, summary)
    metrics = _evaluate(rows, model)
    drift = _drift_summary(summary)
    promotion = {
        "decision": (
            "promote"
            if metrics["accuracy"] >= PROMOTION_MIN_ACCURACY
            and drift["status"] != "blocked"
            else "reject"
        ),
        "criteria": {
            "minimum_training_fixture_accuracy": PROMOTION_MIN_ACCURACY,
            "drift_status_must_not_be": "blocked",
        },
    }
    data_sha256 = _file_sha256(request.training_data_path)
    model_payload = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "model_name": MODEL_NAME,
        "algorithm": ALGORITHM,
        "run_id": request.run_id,
        "train_date": request.train_date,
        "feature_order": list(FEATURES),
        "normalization": model["normalization"],
        "coefficients": model["coefficients"],
        "intercept": model["intercept"],
        "threshold": model["threshold"],
        "training_data": {
            "sha256": data_sha256,
            "row_count": len(rows),
        },
        "evaluation": {
            "scope": "training-fixture",
            "metrics": metrics,
        },
        "drift_summary": drift,
        "promotion": promotion,
    }
    model_payload["model_version"] = _model_version(model_payload)

    keys = _object_keys(request)
    paths = {name: request.output_dir / key for name, key in keys.items()}
    _write_json_atomic(paths["model"], model_payload)
    manifest = {
        "contract_version": 1,
        "dataset": DATASET,
        "model_name": MODEL_NAME,
        "model_schema_version": MODEL_SCHEMA_VERSION,
        "model_version": model_payload["model_version"],
        "run_id": request.run_id,
        "train_date": request.train_date,
        "trained_at": request.trained_at.isoformat(),
        "status": "succeeded",
        "mode": "run_id",
        "training_row_count": len(rows),
        "training_data_sha256": data_sha256,
        "evaluation_scope": "training-fixture",
        "metrics": metrics,
        "drift_summary": drift,
        "promotion": promotion,
        "model_sha256": _file_sha256(paths["model"]),
        "objects": keys,
        "evidence_paths": [keys["model"], keys["manifest"]],
        "artifact_paths": {name: str(path) for name, path in paths.items()},
    }
    _write_json_atomic(paths["manifest"], manifest)
    return manifest


def _validate_request(request: ChurnTrainingRequest) -> None:
    if not _RUN_ID.fullmatch(request.run_id):
        raise ValueError("CHURN_MODEL_RUN_ID must be a safe 1-128 character id")
    try:
        datetime.date.fromisoformat(request.train_date)
    except ValueError as exc:
        raise ValueError("CHURN_MODEL_TRAIN_DATE must use YYYY-MM-DD") from exc


def _load_rows(path: Path) -> list[dict[str, float]]:
    if not path.is_file():
        raise RuntimeError(f"CHURN_TRAINING_DATA_PATH is not a file: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {*FEATURES, "churned"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"training data is missing columns: {', '.join(missing)}")
        rows = [
            {
                **{feature: float(raw[feature]) for feature in FEATURES},
                "churned": float(raw["churned"]),
            }
            for raw in reader
        ]
    if not rows:
        raise RuntimeError(f"no churn training rows found in {path}")
    if any(not math.isfinite(value) for row in rows for value in row.values()) or {
        row["churned"] for row in rows
    } - {0.0, 1.0}:
        raise ValueError("training values must be finite and churned must be 0 or 1")
    if {row["churned"] for row in rows} != {0.0, 1.0}:
        raise ValueError("training data must contain both outcome classes")
    return rows


def _feature_summary(rows: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    return {
        feature: {
            "min": min(row[feature] for row in rows),
            "max": max(row[feature] for row in rows),
            "mean": round(statistics.fmean(row[feature] for row in rows), 6),
            "scale": round(
                max(statistics.pstdev(row[feature] for row in rows), 1e-9), 6
            ),
        }
        for feature in FEATURES
    }


def _build_model(
    rows: list[dict[str, float]], summary: dict[str, dict[str, float]]
) -> dict[str, Any]:
    positives = [row for row in rows if row["churned"] == 1.0]
    negatives = [row for row in rows if row["churned"] == 0.0]
    positive_rate = len(positives) / len(rows)
    return {
        "intercept": round(math.log(positive_rate / (1 - positive_rate)), 6),
        "coefficients": {
            feature: round(
                (
                    statistics.fmean(row[feature] for row in positives)
                    - statistics.fmean(row[feature] for row in negatives)
                )
                / summary[feature]["scale"],
                6,
            )
            for feature in FEATURES
        },
        "normalization": {
            feature: {
                "mean": summary[feature]["mean"],
                "scale": summary[feature]["scale"],
            }
            for feature in FEATURES
        },
        "threshold": 0.5,
    }


def _evaluate(rows: list[dict[str, float]], model: dict[str, Any]) -> dict[str, float]:
    true_positive = true_negative = false_positive = false_negative = 0
    for row in rows:
        predicted = _score(row, model) >= model["threshold"]
        actual = row["churned"] == 1.0
        true_positive += int(predicted and actual)
        true_negative += int(not predicted and not actual)
        false_positive += int(predicted and not actual)
        false_negative += int(not predicted and actual)
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    return {
        "accuracy": round((true_positive + true_negative) / len(rows), 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "positive_rate": round(statistics.fmean(row["churned"] for row in rows), 6),
    }


def _score(row: dict[str, float], model: dict[str, Any]) -> float:
    value = float(model["intercept"])
    for feature in FEATURES:
        normalized = (row[feature] - model["normalization"][feature]["mean"]) / model[
            "normalization"
        ][feature]["scale"]
        value += model["coefficients"][feature] * normalized
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1 + exp_value)


def _drift_summary(
    summary: dict[str, dict[str, float]],
) -> dict[str, Any]:
    standardized_deltas = {
        feature: round(
            (summary[feature]["mean"] - REFERENCE_MEANS[feature])
            / summary[feature]["scale"],
            6,
        )
        for feature in FEATURES
    }
    maximum = max(abs(delta) for delta in standardized_deltas.values())
    return {
        "reference": "checked-in-baseline-v1",
        "standardized_mean_deltas": standardized_deltas,
        "maximum_absolute_delta": round(maximum, 6),
        "status": "blocked" if maximum > 3 else "warning" if maximum > 2 else "ok",
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
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]


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
