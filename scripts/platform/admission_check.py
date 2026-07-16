#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
ADMISSION_ROOT = ROOT / "platform" / "admission"
SCHEMA_PATH = ADMISSION_ROOT / "workload-candidate.schema.json"
RUNTIME_DEFAULTS_PATH = ROOT / "platform" / "runtime-defaults.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise SystemExit(f"{path}: expected JSON object")
    return document


def _format_json_path(path: tuple[Any, ...]) -> str:
    if not path:
        return "$"
    value = "$"
    for part in path:
        value += f"[{part}]" if isinstance(part, int) else f".{part}"
    return value


def _semantic_errors(candidate: dict[str, Any]) -> list[str]:
    runtime_defaults = _load_json(RUNTIME_DEFAULTS_PATH)
    known_targets = set(runtime_defaults["runtime_targets"])
    supported = set(candidate["runtime"]["supported"])
    admitted = set(candidate["runtime"]["admitted"])
    errors: list[str] = []

    for field, targets in (("supported", supported), ("admitted", admitted)):
        unknown = sorted(targets - known_targets)
        if unknown:
            errors.append(
                f"semantic $.runtime.{field}: unknown runtime targets: "
                + ", ".join(unknown)
            )

    unsupported = sorted(admitted - supported)
    if unsupported:
        errors.append(
            "semantic $.runtime.admitted: targets must also be supported: "
            + ", ".join(unsupported)
        )

    declared_config = {key: set(candidate["config"][key]) for key in ("env", "secrets")}
    dependency_names: set[str] = set()
    for index, dependency in enumerate(candidate.get("bounded_dependencies", [])):
        name = dependency["name"]
        if name in dependency_names:
            errors.append(
                f"semantic $.bounded_dependencies[{index}].name: duplicate name {name}"
            )
        dependency_names.add(name)
        for key in ("env", "secrets"):
            undeclared = sorted(set(dependency["config"][key]) - declared_config[key])
            if undeclared:
                errors.append(
                    f"semantic $.bounded_dependencies[{index}].config.{key}: "
                    f"not declared in $.config.{key}: " + ", ".join(undeclared)
                )

    return errors


def validate_candidate(path: Path, validator: Draft202012Validator) -> list[str]:
    candidate = _load_json(path)
    errors = [
        f"schema {_format_json_path(tuple(error.path))}: {error.message}"
        for error in sorted(validator.iter_errors(candidate), key=str)
    ]
    return errors or _semantic_errors(candidate)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate workload candidates against admission contracts."
    )
    parser.add_argument(
        "--candidate",
        required=True,
        help="Path to a draft workload JSON object.",
    )
    parser.add_argument("--format", choices=["table", "json"], default="table")
    args = parser.parse_args(argv)

    schema = _load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    candidate_path = Path(args.candidate)
    rows = [
        {
            "candidate": str(candidate_path),
            "errors": validate_candidate(candidate_path, validator),
        }
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
