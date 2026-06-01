#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CLASS_DEFAULTS: dict[str, dict[str, Any]] = {
    "edge-service": {
        "kind": "service",
        "use_cases": ["http-api"],
        "operational": {"class": "edge-service", "exposure": "public"},
        "service": {"port": 8080},
        "edge": {
            "hostname_label": "<hostname-label>",
            "hostname_label_convention": "explicit-label",
            "auth_mode": "<auth-mode>",
        },
        "metrics": {
            "format": "prometheus",
            "required_names": ["workload_info"],
        },
    },
    "internal-service": {
        "kind": "service",
        "use_cases": ["internal-api"],
        "operational": {"class": "internal-service", "exposure": "internal"},
        "service": {"port": 8080},
        "metrics": {
            "format": "prometheus",
            "required_names": ["workload_info"],
        },
    },
    "operator-job": {
        "kind": "job",
        "use_cases": ["operator-task"],
        "operational": {"class": "operator-job", "trigger": "manual"},
        "job": {"idempotency": "<idempotency-mode>"},
    },
    "scheduled-job": {
        "kind": "job",
        "use_cases": ["scheduled-pipeline"],
        "operational": {"class": "scheduled-job", "trigger": "schedule"},
        "job": {"idempotency": "<idempotency-mode>"},
    },
}

KIND_CLASSES = {
    "service": {"edge-service", "internal-service"},
    "job": {"operator-job", "scheduled-job"},
}


def build_candidate(
    *,
    name: str,
    kind: str,
    operational_class: str,
    owner: str,
) -> dict[str, Any]:
    if kind not in KIND_CLASSES:
        raise ValueError("kind must be service or job")
    if operational_class not in KIND_CLASSES[kind]:
        raise ValueError(f"class {operational_class!r} is not valid for kind {kind!r}")

    repository = name.replace("_", "-")
    defaults = CLASS_DEFAULTS[operational_class]
    candidate: dict[str, Any] = {
        "name": name,
        "kind": kind,
        "use_cases": list(defaults["use_cases"]),
        "owner": owner,
        "runtime": {"supported": ["local-compose"], "admitted": []},
        "operational": dict(defaults["operational"]),
        "image": {
            "repository": repository,
            "package": repository,
            "command": f"python -m {name}.main",
        },
        "traces": {"supported": False},
        "config": {"env": [], "secrets": []},
    }
    for key in ["service", "edge", "metrics", "job"]:
        if key in defaults:
            candidate[key] = dict(defaults[key])
    return candidate


def _write_candidate(candidate: dict[str, Any], output: str | None) -> None:
    text = json.dumps(candidate, indent=2, sort_keys=False) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the smallest draft workload contract candidate."
    )
    parser.add_argument("--name", required=True)
    parser.add_argument("--kind", choices=["service", "job"], required=True)
    parser.add_argument("--class", dest="operational_class", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        candidate = build_candidate(
            name=args.name,
            kind=args.kind,
            operational_class=args.operational_class,
            owner=args.owner,
        )
    except ValueError as exc:
        parser.error(str(exc))

    _write_candidate(candidate, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
