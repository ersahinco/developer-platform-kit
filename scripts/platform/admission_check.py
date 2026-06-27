#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.workload_fit_check import evaluate_candidate  # noqa: E402


ADMISSION_ROOT = ROOT / "platform" / "admission"
SCHEMA_PATH = ADMISSION_ROOT / "workload-candidate.schema.json"
CANDIDATES_ROOT = ADMISSION_ROOT / "candidates"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise SystemExit(f"{path}: expected JSON object")
    return document


def _candidate_paths(candidate: str | None) -> list[Path]:
    if candidate:
        return [Path(candidate)]
    return sorted(CANDIDATES_ROOT.glob("*.json"))


def _format_json_path(path: tuple[Any, ...]) -> str:
    if not path:
        return "$"
    value = "$"
    for part in path:
        value += f"[{part}]" if isinstance(part, int) else f".{part}"
    return value


def validate_candidate(path: Path, validator: Draft202012Validator) -> list[str]:
    candidate = _load_json(path)
    errors = [
        f"schema {_format_json_path(tuple(error.path))}: {error.message}"
        for error in sorted(validator.iter_errors(candidate), key=str)
    ]
    fit_results = evaluate_candidate(candidate)
    errors.extend(
        f"fit {result.area}: {result.message}"
        for result in fit_results
        if result.status == "fail"
    )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate repo-owned workload admission candidates."
    )
    parser.add_argument(
        "--candidate",
        help="Validate one candidate path instead of platform/admission/candidates/*.json.",
    )
    parser.add_argument("--format", choices=["table", "json"], default="table")
    args = parser.parse_args(argv)

    schema = _load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    rows = [
        {"candidate": str(path), "errors": validate_candidate(path, validator)}
        for path in _candidate_paths(args.candidate)
    ]

    if args.format == "json":
        print(json.dumps(rows, sort_keys=True))
    else:
        for row in rows:
            errors = row["errors"]
            print(f"{row['candidate']}\t{'ok' if not errors else 'fail'}")
            for error in errors:
                print(f"- {error}")

    return 1 if any(row["errors"] for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
