#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.platform.workload_fit_check import evaluate_candidate  # noqa: E402

SERVICE_PROOF = (
    "/health",
    "/ready",
    "/metrics with workload_info",
    "declared config env/secrets",
    "structured workload logs",
)

JOB_PROOF = (
    "process exit status",
    "terminal event",
    "idempotency mode",
    "declared config env/secrets",
)


@dataclass(frozen=True)
class LocalProofPlan:
    fit: bool
    local_proof: str
    add: list[str]
    prove: list[str]
    blocked_by: list[str]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_candidate(path: Path) -> dict[str, Any]:
    document = _load_json(path)
    if not isinstance(document, dict):
        raise SystemExit("candidate JSON must be one workload object")
    return document


def _workload_contract() -> dict[str, Any]:
    return _load_json(ROOT / "platform" / "workloads.json")


def _runtime_conformance() -> dict[str, Any]:
    return _load_json(ROOT / "platform" / "runtime-conformance.json")


def _compose_services() -> dict[str, Any]:
    services: dict[str, Any] = {}
    in_services = False
    for line in (ROOT / "compose.yaml").read_text(encoding="utf-8").splitlines():
        if line == "services:":
            in_services = True
            continue
        if not in_services:
            continue
        if line and not line.startswith(" "):
            break
        match = re.fullmatch(r"  ([A-Za-z0-9_-]+):", line)
        if match:
            services[match.group(1)] = {}
    return services


def _candidate_app_path(candidate: dict[str, Any]) -> str:
    app_path = candidate.get("app_path")
    if isinstance(app_path, str) and app_path:
        return app_path
    return f"apps/{candidate['name']}"


def _candidate_repository(candidate: dict[str, Any]) -> str:
    image = candidate.get("image", {})
    if isinstance(image, dict):
        repository = image.get("repository")
        if isinstance(repository, str) and repository:
            return repository
    return str(candidate["name"]).replace("_", "-")


def _registered_local_workload(candidate: dict[str, Any]) -> bool:
    contract = _workload_contract()
    for workload in contract.get("workloads", []):
        if not isinstance(workload, dict):
            continue
        if workload.get("name") != candidate.get("name"):
            continue
        runtime = workload.get("runtime", {})
        supported = runtime.get("supported", []) if isinstance(runtime, dict) else []
        return "local-compose" in supported
    return False


def _missing_additions(candidate: dict[str, Any]) -> list[str]:
    name = str(candidate["name"])
    app_path = _candidate_app_path(candidate)
    repository = _candidate_repository(candidate)
    runtime_conformance = _runtime_conformance()
    additions: list[str] = []

    if not _registered_local_workload(candidate):
        additions.append("platform/workloads.json entry")
    for filename in ["config.py", "main.py", "pyproject.toml"]:
        path = ROOT / app_path / filename
        if not path.is_file():
            additions.append(f"{app_path}/{filename}")
    if repository not in _compose_services():
        additions.append(f"compose service {repository}")
    workloads = runtime_conformance.get("workloads", {})
    if not isinstance(workloads, dict) or name not in workloads:
        additions.append("platform/runtime-conformance.json fixture")
    return additions


def _proof_items(candidate: dict[str, Any]) -> list[str]:
    if candidate.get("kind") == "service":
        return list(SERVICE_PROOF)
    return list(JOB_PROOF)


def build_local_proof_plan(candidate: dict[str, Any]) -> LocalProofPlan:
    fit_results = evaluate_candidate(candidate)
    failures = [
        f"{result.area}: {result.message}"
        for result in fit_results
        if result.status == "fail"
    ]
    if failures:
        return LocalProofPlan(
            fit=False,
            local_proof="blocked",
            add=[],
            prove=[],
            blocked_by=failures,
        )

    additions = _missing_additions(candidate)
    return LocalProofPlan(
        fit=True,
        local_proof="ready" if not additions else "not ready",
        add=additions,
        prove=_proof_items(candidate),
        blocked_by=[],
    )


def _print_plan(plan: LocalProofPlan) -> None:
    print(f"fit: {'yes' if plan.fit else 'no'}")
    print(f"local proof: {plan.local_proof}")
    if plan.blocked_by:
        print("blocked by:")
        for item in plan.blocked_by:
            print(f"- {item}")
        print("next make workload-fit-check")
        return

    print("add:")
    if plan.add:
        for item in plan.add:
            print(f"- {item}")
    else:
        print("- none")

    print("prove:")
    for item in plan.prove:
        print(f"- {item}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan the shortest local proof path for a passing workload candidate."
    )
    parser.add_argument(
        "--candidate",
        default=os.environ.get("WORKLOAD_CANDIDATE"),
        help="Path to a draft workload JSON object. Defaults to WORKLOAD_CANDIDATE.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    if not args.candidate:
        print(
            "set WORKLOAD_CANDIDATE=<path> or pass --candidate <path>",
            file=sys.stderr,
        )
        return 2

    candidate = _load_candidate(Path(args.candidate))
    plan = build_local_proof_plan(candidate)
    if args.format == "json":
        print(json.dumps(asdict(plan), sort_keys=True))
    else:
        _print_plan(plan)
    return 1 if not plan.fit else 0


if __name__ == "__main__":
    raise SystemExit(main())
