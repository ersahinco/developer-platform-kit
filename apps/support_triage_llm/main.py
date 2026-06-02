from __future__ import annotations

import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from typing import cast

from fastapi import FastAPI
from fastapi import Request
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import Counter
from prometheus_client import generate_latest
from prometheus_client import Histogram
from starlette.responses import JSONResponse
from starlette.responses import Response
import uvicorn

from infrastructure.http_health import health_payload
from infrastructure.http_observability import request_observability_middleware
from infrastructure.workload_observability import ensure_workload_info_metric
from support_triage_llm.config import settings
from support_triage_llm.engine import LOCAL_MODEL_NAME
from support_triage_llm.engine import estimated_cost_usd
from support_triage_llm.engine import evaluate_cases
from support_triage_llm.engine import evaluation_status
from support_triage_llm.engine import load_eval_cases
from support_triage_llm.engine import load_prompt
from support_triage_llm.engine import run_triage
from support_triage_llm.engine import token_evidence
from support_triage_llm.evidence import evaluation_completed_event
from support_triage_llm.evidence import failed_operator_payload
from support_triage_llm.evidence import triage_completed_event
from support_triage_llm.evidence import write_evidence
from support_triage_llm.schemas import EvalRequest
from support_triage_llm.schemas import TriageRequest

WORKLOAD_NAME = "support_triage_llm"
WORKLOAD_CLASS = "internal-service"

REQUEST_COUNT = Counter(
    "support_triage_llm_http_requests_total",
    "Support triage LLM HTTP requests by method, route, and status code.",
    ["method", "route", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "support_triage_llm_http_request_duration_seconds",
    "Support triage LLM HTTP request latency by method and route.",
    ["method", "route"],
)
TRIAGE_COUNT = Counter(
    "support_triage_llm_requests_total",
    "Support triage requests by prompt version and status.",
    ["prompt_version", "status"],
)
TRIAGE_LATENCY = Histogram(
    "support_triage_llm_latency_seconds",
    "Support triage latency by prompt version.",
    ["prompt_version"],
)
TRIAGE_TOKEN_COUNT = Counter(
    "support_triage_llm_tokens_total",
    "Support triage token estimates by prompt version and token direction.",
    ["prompt_version", "direction"],
)
TRIAGE_COST = Counter(
    "support_triage_llm_cost_usd_total",
    "Support triage estimated cost by prompt version.",
    ["prompt_version"],
)
ensure_workload_info_metric(workload=WORKLOAD_NAME, workload_class=WORKLOAD_CLASS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        prompt = load_prompt(Path(settings.support_triage_prompt_path))
        eval_cases = load_eval_cases(Path(settings.support_triage_eval_cases_path))
        output_dir = Path(settings.support_triage_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        app.state.prompt = prompt
        app.state.eval_cases = eval_cases
        app.state.output_dir = output_dir
        app.state.load_error = None
    except Exception as exc:  # noqa: BLE001
        app.state.prompt = None
        app.state.eval_cases = []
        app.state.output_dir = Path(settings.support_triage_output_dir)
        app.state.load_error = str(exc)
    yield


app = FastAPI(title="support-triage-llm", lifespan=lifespan)


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
    prompt = getattr(request.app.state, "prompt", None)
    if prompt is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "checks": {
                    "prompt": getattr(request.app.state, "load_error", "not loaded")
                },
            },
        )
    return {
        "status": "ready",
        "checks": {
            "prompt": "ok",
            "evaluation_cases": "ok",
            "output_dir": "ok",
        },
        "prompt_version": prompt["prompt_version"],
    }


@app.post("/triage", response_model=None)
def triage(
    payload: TriageRequest, request: Request
) -> dict[str, object] | JSONResponse:
    prompt = getattr(request.app.state, "prompt", None)
    if prompt is None:
        run_id = payload.run_id or _new_run_id()
        event = failed_operator_payload(
            output_dir=Path(request.app.state.output_dir),
            run_id=run_id,
            reason=getattr(request.app.state, "load_error", "prompt not loaded"),
        )
        return JSONResponse(status_code=503, content=event)

    prompt = cast(dict[str, str], prompt)
    run_id = payload.run_id or _new_run_id()
    started = time.perf_counter()
    result = run_triage(prompt=prompt, payload=payload)
    elapsed = time.perf_counter() - started
    token_counts = token_evidence(
        prompt_text=prompt["prompt_text"],
        payload=payload,
        result=result,
    )
    cost_usd = estimated_cost_usd(token_counts)
    prompt_version = prompt["prompt_version"]
    TRIAGE_COUNT.labels(prompt_version=prompt_version, status="succeeded").inc()
    TRIAGE_LATENCY.labels(prompt_version=prompt_version).observe(elapsed)
    TRIAGE_TOKEN_COUNT.labels(prompt_version=prompt_version, direction="input").inc(
        token_counts["input_tokens"]
    )
    TRIAGE_TOKEN_COUNT.labels(prompt_version=prompt_version, direction="output").inc(
        token_counts["output_tokens"]
    )
    TRIAGE_COST.labels(prompt_version=prompt_version).inc(cost_usd)
    evidence = triage_completed_event(
        run_id=run_id,
        ticket_id=payload.ticket_id,
        prompt=prompt,
        model_name=LOCAL_MODEL_NAME,
        latency_ms=round(elapsed * 1000, 3),
        token_counts=token_counts,
        estimated_cost_usd=cost_usd,
        result=result,
    )
    evidence_path = write_evidence(
        output_dir=Path(request.app.state.output_dir),
        run_id=run_id,
        payload=evidence,
    )
    event = {**evidence, "evidence_path": evidence_path}
    print(json.dumps(event, sort_keys=True), flush=True)
    return event


@app.post("/evaluate", response_model=None)
def evaluate(
    payload: EvalRequest, request: Request
) -> dict[str, object] | JSONResponse:
    prompt = getattr(request.app.state, "prompt", None)
    if prompt is None:
        run_id = payload.run_id or _new_run_id(prefix="eval")
        event = failed_operator_payload(
            output_dir=Path(request.app.state.output_dir),
            run_id=run_id,
            reason=getattr(request.app.state, "load_error", "prompt not loaded"),
        )
        return JSONResponse(status_code=503, content=event)

    prompt = cast(dict[str, str], prompt)
    run_id = payload.run_id or _new_run_id(prefix="eval")
    eval_cases = cast(list[dict[str, Any]], request.app.state.eval_cases)
    started = time.perf_counter()
    results = evaluate_cases(prompt=prompt, eval_cases=eval_cases, run_id=run_id)
    elapsed = time.perf_counter() - started
    evidence = evaluation_completed_event(
        run_id=run_id,
        prompt=prompt,
        model_name=LOCAL_MODEL_NAME,
        latency_ms=round(elapsed * 1000, 3),
        status=evaluation_status(results),
        results=results,
    )
    evidence_path = write_evidence(
        output_dir=Path(request.app.state.output_dir),
        run_id=run_id,
        payload=evidence,
        prefix="evaluations",
    )
    event = {**evidence, "evidence_path": evidence_path}
    print(json.dumps(event, sort_keys=True), flush=True)
    return event


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _new_run_id(prefix: str = "triage") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)


if __name__ == "__main__":
    main()
