from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any
from typing import cast

from support_triage_llm.schemas import TriageRequest

LOCAL_MODEL_NAME = "deterministic-support-triage-v1"
INPUT_TOKEN_COST_USD = 0.00000015
OUTPUT_TOKEN_COST_USD = 0.0000006


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


def evaluate_cases(
    *,
    prompt: dict[str, str],
    eval_cases: list[dict[str, Any]],
    run_id: str,
) -> list[dict[str, Any]]:
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
    return results


def evaluation_status(results: list[dict[str, Any]]) -> str:
    passed_count = sum(1 for result in results if result["passed"])
    return "succeeded" if passed_count == len(results) else "failed"


def token_evidence(
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


def estimated_cost_usd(token_counts: dict[str, int]) -> float:
    return round(
        token_counts["input_tokens"] * INPUT_TOKEN_COST_USD
        + token_counts["output_tokens"] * OUTPUT_TOKEN_COST_USD,
        8,
    )


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


def _estimate_tokens(value: str) -> int:
    return max(1, math.ceil(len(value.split()) * 1.3))
