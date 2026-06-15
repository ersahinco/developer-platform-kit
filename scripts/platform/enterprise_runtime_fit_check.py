#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

ENTERPRISE_RUNTIME = "enterprise-runtime-candidate"
ENTERPRISE_RUNTIME_OWNED_SEAMS = [
    "platform/runtime-defaults.json",
    "docs/runtime-defaults.md",
    "future enterprise runtime catalog",
]


@dataclass(frozen=True)
class PromotionRequirement:
    name: str
    status: str
    evidence: str


@dataclass(frozen=True)
class EnterpriseCapabilityFit:
    runtime_target: str
    capability: str
    status: str
    candidate_only: bool
    required_evidence: list[str]
    owned_seams: list[str]
    missing_conformance_checks: list[str]
    promotion_gate: list[PromotionRequirement]


def _read_json(path: str) -> dict[str, Any]:
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _promotion_gate(capability: str) -> list[PromotionRequirement]:
    return [
        PromotionRequirement(
            name="owner",
            status="missing",
            evidence="replace future-runtime-owner-required with named runtime owner",
        ),
        PromotionRequirement(
            name="config_surface",
            status="missing",
            evidence=(
                f"add runtime-owned config surface for {capability}; "
                "keep product fields out of platform/workloads.json"
            ),
        ),
        PromotionRequirement(
            name="conformance_test",
            status="missing",
            evidence=f"add enterprise-runtime-candidate conformance for {capability}",
        ),
        PromotionRequirement(
            name="evidence_artifact",
            status="missing",
            evidence=f"define standard evidence artifact for {capability}",
        ),
        PromotionRequirement(
            name="failure_mode",
            status="missing",
            evidence=f"document operator-visible failure mode for {capability}",
        ),
        PromotionRequirement(
            name="runbook",
            status="missing",
            evidence=f"add runtime-owned runbook for {capability}",
        ),
    ]


def _missing_conformance_checks(capability: str) -> list[str]:
    expected = {
        f"enterprise_runtime_{capability}_runtime_check": (
            f"tests/runtime enterprise {capability} check"
        ),
        f"enterprise_runtime_{capability}_contract": (
            f"tests/contracts enterprise {capability} contract"
        ),
        f"enterprise_runtime_{capability}_evidence_fixture": (
            f"operator evidence fixture for {capability}"
        ),
    }
    existing_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for root in [ROOT / "tests" / "runtime", ROOT / "tests" / "contracts"]
        for path in root.rglob("*.py")
    )
    return [
        description
        for marker, description in expected.items()
        if marker not in existing_text
    ]


def enterprise_fit_rows() -> list[EnterpriseCapabilityFit]:
    runtime_defaults = _read_json("platform/runtime-defaults.json")
    active_targets = set(runtime_defaults.get("runtime_targets", {}))
    profile = runtime_defaults["candidate_runtime_profiles"][ENTERPRISE_RUNTIME]

    fits: list[EnterpriseCapabilityFit] = []
    for _area, default in sorted(profile["defaults"].items()):
        capability = default["capability"]
        candidate_only = ENTERPRISE_RUNTIME not in active_targets
        missing = _missing_conformance_checks(capability)
        gate = _promotion_gate(capability)
        fits.append(
            EnterpriseCapabilityFit(
                runtime_target=ENTERPRISE_RUNTIME,
                capability=capability,
                status="candidate-only" if candidate_only else "active",
                candidate_only=candidate_only,
                required_evidence=list(default["evidence"]),
                owned_seams=ENTERPRISE_RUNTIME_OWNED_SEAMS,
                missing_conformance_checks=missing,
                promotion_gate=gate,
            )
        )
    return fits


def _print_text(rows: list[EnterpriseCapabilityFit]) -> None:
    print("enterprise runtime fit: not ready")
    print(
        "promotion gate: "
        "owner, config surface, conformance test, evidence artifact, failure mode, runbook"
    )
    for row in rows:
        print(f"{row.status:<14} {row.runtime_target} {row.capability}")
        print("  required evidence: " + ", ".join(row.required_evidence))
        print("  seams to own: " + ", ".join(row.owned_seams))
        print("  missing conformance: " + ", ".join(row.missing_conformance_checks))
        for requirement in row.promotion_gate:
            print(
                f"  gate {requirement.name}: "
                f"{requirement.status} - {requirement.evidence}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show the enterprise runtime candidate promotion checklist."
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    rows = enterprise_fit_rows()
    if args.format == "json":
        print(json.dumps([asdict(row) for row in rows], indent=2))
    else:
        _print_text(rows)
    return 1 if any(not row.candidate_only for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
