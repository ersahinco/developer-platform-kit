from __future__ import annotations

import json
import math
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from typing import cast

from fastapi import FastAPI
from fastapi import Request
from pydantic import BaseModel
from pydantic import Field
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import Counter
from prometheus_client import generate_latest
from prometheus_client import Histogram
from starlette.responses import JSONResponse
from starlette.responses import Response
import uvicorn

from churn_prediction_api.config import settings
from infrastructure.http_health import health_payload
from infrastructure.http_observability import request_observability_middleware
from infrastructure.workload_observability import ensure_workload_info_metric

WORKLOAD_NAME = "churn_prediction_api"
WORKLOAD_CLASS = "internal-service"

REQUEST_COUNT = Counter(
    "churn_prediction_api_http_requests_total",
    "Churn prediction API HTTP requests by method, route, and status code.",
    ["method", "route", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "churn_prediction_api_http_request_duration_seconds",
    "Churn prediction API HTTP request latency by method and route.",
    ["method", "route"],
)
PREDICTION_COUNT = Counter(
    "churn_prediction_requests_total",
    "Churn prediction requests by model version and status.",
    ["model_version", "status"],
)
PREDICTION_LATENCY = Histogram(
    "churn_prediction_latency_seconds",
    "Churn prediction latency by model version.",
    ["model_version"],
)
ensure_workload_info_metric(workload=WORKLOAD_NAME, workload_class=WORKLOAD_CLASS)


class PredictionRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    tenure_months: float
    monthly_charges: float
    support_tickets_90d: float
    late_payments_12m: float
    usage_drop_pct: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.churn_model = load_model(Path(settings.churn_model_path))
        app.state.model_error = None
    except Exception as exc:  # noqa: BLE001
        app.state.churn_model = None
        app.state.model_error = str(exc)
    yield


app = FastAPI(title="churn-prediction-api", lifespan=lifespan)


def _http_request_event(
    request: Request,
    response: Response,
    request_id: str,
    elapsed_seconds: float,
) -> dict[str, object]:
    return {
        "workload": WORKLOAD_NAME,
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "route": getattr(request.scope.get("route"), "path", request.url.path),
        "status": "succeeded" if response.status_code < 500 else "failed",
        "status_code": response.status_code,
        "duration_ms": round(elapsed_seconds * 1000, 3),
    }


app.middleware("http")(
    request_observability_middleware(
        request_count=REQUEST_COUNT,
        request_latency=REQUEST_LATENCY,
        event_payload=_http_request_event,
    )
)


@app.get("/health")
def health() -> dict[str, str]:
    return health_payload()


@app.get("/ready", response_model=None)
def ready(request: Request) -> dict[str, object] | JSONResponse:
    if getattr(request.app.state, "churn_model", None) is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "checks": {
                    "model": getattr(request.app.state, "model_error", "not loaded")
                },
            },
        )
    model = cast(dict[str, Any], request.app.state.churn_model)
    return {
        "status": "ready",
        "checks": {"model": "ok"},
        "model_version": model["model_version"],
        "run_id": model["run_id"],
    }


@app.post("/predict")
def predict(payload: PredictionRequest, request: Request) -> dict[str, object]:
    model = getattr(request.app.state, "churn_model", None)
    if model is None:
        PREDICTION_COUNT.labels(model_version="unloaded", status="failed").inc()
        return cast(
            dict[str, object],
            JSONResponse(
                status_code=503,
                content={"status": "failed", "error": "model not loaded"},
            ),
        )

    model = cast(dict[str, Any], model)
    started = time.perf_counter()
    probability = score_churn(model=model, features=payload.model_dump())
    elapsed = time.perf_counter() - started
    status = "succeeded"
    model_version = str(model["model_version"])
    PREDICTION_COUNT.labels(model_version=model_version, status=status).inc()
    PREDICTION_LATENCY.labels(model_version=model_version).observe(elapsed)
    event = {
        "workload": WORKLOAD_NAME,
        "event": "churn_prediction",
        "status": status,
        "customer_id": payload.customer_id,
        "model_version": model_version,
        "run_id": model["run_id"],
        "duration_ms": round(elapsed * 1000, 3),
    }
    print(json.dumps(event, sort_keys=True), flush=True)
    return {
        "status": status,
        "customer_id": payload.customer_id,
        "model_version": model_version,
        "run_id": model["run_id"],
        "churn_probability": round(probability, 6),
        "prediction": "churn_risk" if probability >= model["threshold"] else "retain",
    }


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)


if __name__ == "__main__":
    main()
