from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

WORKLOAD_NAME = "support_triage_llm"


def write_evidence(
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


def triage_completed_event(
    *,
    run_id: str,
    ticket_id: str,
    prompt: dict[str, str],
    model_name: str,
    latency_ms: float,
    token_counts: dict[str, int],
    estimated_cost_usd: float,
    result: dict[str, object],
) -> dict[str, Any]:
    return {
        "workload": WORKLOAD_NAME,
        "event": "support_triage_completed",
        "status": "succeeded",
        "run_id": run_id,
        "ticket_id": ticket_id,
        "prompt_version": prompt["prompt_version"],
        "prompt_sha256": prompt["prompt_sha256"],
        "model_name": model_name,
        "latency_ms": latency_ms,
        "token_evidence": token_counts,
        "estimated_cost_usd": estimated_cost_usd,
        **result,
    }


def evaluation_completed_event(
    *,
    run_id: str,
    prompt: dict[str, str],
    model_name: str,
    latency_ms: float,
    status: str,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    passed_count = sum(1 for result in results if result["passed"])
    return {
        "workload": WORKLOAD_NAME,
        "event": "support_triage_evaluation_completed",
        "status": status,
        "run_id": run_id,
        "prompt_version": prompt["prompt_version"],
        "prompt_sha256": prompt["prompt_sha256"],
        "model_name": model_name,
        "latency_ms": latency_ms,
        "case_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "results": results,
    }


def failed_operator_payload(
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
    evidence_path = write_evidence(
        output_dir=output_dir,
        run_id=run_id,
        payload=event,
        prefix="operator-payloads",
    )
    event["evidence_path"] = evidence_path
    print(json.dumps(event, sort_keys=True), flush=True)
    return event
