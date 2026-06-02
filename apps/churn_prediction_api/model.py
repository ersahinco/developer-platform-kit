from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
from typing import cast


def load_model(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"CHURN_MODEL_PATH is not a file: {path}")
    model = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "model_name",
        "model_version",
        "run_id",
        "features",
        "weights",
        "intercept",
        "threshold",
    }
    missing = sorted(required - set(model))
    if missing:
        raise RuntimeError(f"churn model is missing fields: {', '.join(missing)}")
    return cast(dict[str, Any], model)


def score_churn(*, model: dict[str, Any], features: dict[str, Any]) -> float:
    z = float(model["intercept"])
    for feature, weight in model["weights"].items():
        z += float(weight) * float(features[feature])
    return 1 / (1 + math.exp(-z))
