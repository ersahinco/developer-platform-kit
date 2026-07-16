from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
from typing import cast

MODEL_SCHEMA_VERSION = 1


def load_model(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"CHURN_MODEL_PATH is not a file: {path}")
    model = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(model, dict):
        raise RuntimeError("churn model must be a JSON object")
    required = {
        "schema_version",
        "model_name",
        "model_version",
        "run_id",
        "feature_order",
        "normalization",
        "coefficients",
        "intercept",
        "threshold",
        "training_data",
        "promotion",
    }
    missing = sorted(required - set(model))
    if missing:
        raise RuntimeError(f"churn model is missing fields: {', '.join(missing)}")
    if model["schema_version"] != MODEL_SCHEMA_VERSION:
        raise RuntimeError(
            f"unsupported churn model schema_version: {model['schema_version']}"
        )
    features = model["feature_order"]
    if (
        not isinstance(features, list)
        or not features
        or len(features) != len(set(features))
    ):
        raise RuntimeError("churn model feature_order must be a unique string list")
    if not all(isinstance(feature, str) for feature in features):
        raise RuntimeError("churn model feature_order must contain strings")
    if set(model["coefficients"]) != set(features) or set(
        model["normalization"]
    ) != set(features):
        raise RuntimeError("churn model feature contract is inconsistent")
    numeric_values = [model["intercept"], model["threshold"]]
    for feature in features:
        numeric_values.extend(
            [
                model["coefficients"][feature],
                model["normalization"][feature]["mean"],
                model["normalization"][feature]["scale"],
            ]
        )
        if model["normalization"][feature]["scale"] <= 0:
            raise RuntimeError(f"churn model scale must be positive: {feature}")
    if not all(math.isfinite(float(value)) for value in numeric_values):
        raise RuntimeError("churn model numeric values must be finite")
    if not 0 < float(model["threshold"]) < 1:
        raise RuntimeError("churn model threshold must be between 0 and 1")
    if model["promotion"].get("decision") != "promote":
        raise RuntimeError("churn model has not passed its promotion gate")
    return cast(dict[str, Any], model)


def score_churn(*, model: dict[str, Any], features: dict[str, Any]) -> float:
    required = model["feature_order"]
    missing = sorted(set(required) - set(features))
    if missing:
        raise ValueError(f"prediction is missing features: {', '.join(missing)}")
    value = float(model["intercept"])
    for feature in required:
        normalization = model["normalization"][feature]
        normalized = (float(features[feature]) - float(normalization["mean"])) / float(
            normalization["scale"]
        )
        value += float(model["coefficients"][feature]) * normalized
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1 + exp_value)
