from __future__ import annotations

import datetime
import hashlib
import json
import math
import re
import time
import uuid
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

from infrastructure.http_health import health_payload
from infrastructure.http_observability import request_observability_middleware
from infrastructure.workload_observability import ensure_workload_info_metric
from support_triage_llm.config import settings

WORKLOAD_NAME = "support_triage_llm"
WORKLOAD_CLASS = "internal-service"
LOCAL_MODEL_NAME = "deterministic-support-triage-v1"
INPUT_TOKEN_COST_USD = 0.00000015
OUTPUT_TOKEN_COST_USD = 0.0000006

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


class TriageRequest(BaseModel):
    ticket_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    customer_tier: str = "standard"
    run_id: str | None = None


class EvalRequest(BaseModel):
    run_id: str | None = None


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
        event = _failed_operator_payload(
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
    token_evidence = _token_evidence(
        prompt_text=prompt["prompt_text"],
        payload=payload,
        result=result,
    )
    cost_usd = _estimated_cost_usd(token_evidence)
    prompt_version = prompt["prompt_version"]
    TRIAGE_COUNT.labels(prompt_version=prompt_version, status="succeeded").inc()
    TRIAGE_LATENCY.labels(prompt_version=prompt_version).observe(elapsed)
    TRIAGE_TOKEN_COUNT.labels(prompt_version=prompt_version, direction="input").inc(
        token_evidence["input_tokens"]
    )
    TRIAGE_TOKEN_COUNT.labels(prompt_version=prompt_version, direction="output").inc(
        token_evidence["output_tokens"]
    )
    TRIAGE_COST.labels(prompt_version=prompt_version).inc(cost_usd)
    evidence = {
        "workload": WORKLOAD_NAME,
        "event": "support_triage_completed",
        "status": "succeeded",
        "run_id": run_id,
        "ticket_id": payload.ticket_id,
        "prompt_version": prompt_version,
        "prompt_sha256": prompt["prompt_sha256"],
        "model_name": LOCAL_MODEL_NAME,
        "latency_ms": round(elapsed * 1000, 3),
        "token_evidence": token_evidence,
        "estimated_cost_usd": cost_usd,
        **result,
    }
    evidence_path = _write_evidence(
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
        event = _failed_operator_payload(
            output_dir=Path(request.app.state.output_dir),
            run_id=run_id,
            reason=getattr(request.app.state, "load_error", "prompt not loaded"),
        )
        return JSONResponse(status_code=503, content=event)

    prompt = cast(dict[str, str], prompt)
    run_id = payload.run_id or _new_run_id(prefix="eval")
    eval_cases = cast(list[dict[str, Any]], request.app.state.eval_cases)
    started = time.perf_counter()
    results = []
    for case in eval_cases:
        triage_request = TriageRequest(**case["input"], run_id=run_id)
        actual = run_triage(prompt=prompt, payload=triage_request)
        expected = case["expected"]
        results.append(
            {
                "case_id": case["case_id"],
                "passed": actual["category"] == expected["category"]
                and actual["priority"] == expected["priority"],
                "actual": {
                    "category": actual["category"],
                    "priority": actual["priority"],
                },
                "expected": expected,
            }
        )
    elapsed = time.perf_counter() - started
    passed_count = sum(1 for result in results if result["passed"])
    status = "succeeded" if passed_count == len(results) else "failed"
    evidence = {
        "workload": WORKLOAD_NAME,
        "event": "support_triage_evaluation_completed",
        "status": status,
        "run_id": run_id,
        "prompt_version": prompt["prompt_version"],
        "prompt_sha256": prompt["prompt_sha256"],
        "model_name": LOCAL_MODEL_NAME,
        "latency_ms": round(elapsed * 1000, 3),
        "case_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "results": results,
    }
    evidence_path = _write_evidence(
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


def load_prompt(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise RuntimeError(f"SUPPORT_TRIAGE_PROMPT_PATH is not a file: {path}")
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^version:\s*(?P<version>[a-zA-Z0-9_.-]+)\s*$", text, re.M)
    if match is None:
        raise RuntimeError("support triage prompt must declare a version line")
    return {
        "prompt_version": match.group("version"),
        "prompt_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "prompt_text": text,
    }


def load_eval_cases(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"SUPPORT_TRIAGE_EVAL_CASES_PATH is not a file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise RuntimeError("support triage evaluation cases must be a non-empty list")
    return cast(list[dict[str, Any]], data)


def run_triage(*, prompt: dict[str, str], payload: TriageRequest) -> dict[str, object]:
    text = f"{payload.subject}\n{payload.body}".lower()
    category = _category(text)
    priority = _priority(text=text, customer_tier=payload.customer_tier)
    summary = f"{category} request for {payload.customer_tier} customer"
    suggested_action = _suggested_action(category=category, priority=priority)
    return {
        "category": category,
        "priority": priority,
        "summary": summary,
        "suggested_action": suggested_action,
        "prompt_version": prompt["prompt_version"],
    }


def _category(text: str) -> str:
    if any(word in text for word in ["refund", "invoice", "billing", "charge"]):
        return "billing"
    if any(word in text for word in ["down", "outage", "unavailable", "error"]):
        return "incident"
    if any(word in text for word in ["password", "login", "access", "sso"]):
        return "access"
    return "general"


def _priority(*, text: str, customer_tier: str) -> str:
    if "production" in text or "outage" in text or "down" in text:
        return "urgent"
    if customer_tier.lower() in {"enterprise", "premium"}:
        return "high"
    if "refund" in text or "login" in text:
        return "medium"
    return "low"


def _suggested_action(*, category: str, priority: str) -> str:
    if priority == "urgent":
        return "page on-call and attach operator payload"
    if category == "billing":
        return "route to billing queue with account context"
    if category == "access":
        return "route to identity support with login diagnostics"
    return "route to support queue"


def _token_evidence(
    *,
    prompt_text: str,
    payload: TriageRequest,
    result: dict[str, object],
) -> dict[str, int]:
    input_text = " ".join(
        [
            prompt_text,
            payload.subject,
            payload.body,
            payload.customer_tier,
        ]
    )
    output_text = json.dumps(result, sort_keys=True)
    return {
        "input_tokens": _estimate_tokens(input_text),
        "output_tokens": _estimate_tokens(output_text),
    }


def _estimate_tokens(value: str) -> int:
    return max(1, math.ceil(len(value.split()) * 1.3))


def _estimated_cost_usd(token_evidence: dict[str, int]) -> float:
    return round(
        token_evidence["input_tokens"] * INPUT_TOKEN_COST_USD
        + token_evidence["output_tokens"] * OUTPUT_TOKEN_COST_USD,
        8,
    )


def _write_evidence(
    *,
    output_dir: Path,
    run_id: str,
    payload: dict[str, Any],
    prefix: str = "runs",
) -> str:
    key = f"support_triage_llm/{prefix}/{run_id}.json"
    path = output_dir / key
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    persisted = {**payload, "evidence_path": key}
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(persisted, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)
    return key


def _failed_operator_payload(
    *, output_dir: Path, run_id: str, reason: str
) -> dict[str, Any]:
    event = {
        "workload": WORKLOAD_NAME,
        "event": "support_triage_failed",
        "status": "failed",
        "run_id": run_id,
        "mode": "operator_payload",
        "timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "reason": reason,
    }
    evidence_path = _write_evidence(
        output_dir=output_dir,
        run_id=run_id,
        payload=event,
        prefix="operator-payloads",
    )
    event["evidence_path"] = evidence_path
    print(json.dumps(event, sort_keys=True), flush=True)
    return event


def _new_run_id(prefix: str = "triage") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)


if __name__ == "__main__":
    main()
