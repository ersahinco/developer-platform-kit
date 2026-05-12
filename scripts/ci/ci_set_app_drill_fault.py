#!/usr/bin/env python3
"""Set app rollback-drill fault injection environment variables."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _load_task_definition(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_task_definition(path: Path, task_definition: dict[str, Any]) -> None:
    path.write_text(json.dumps(task_definition, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: ci_set_app_drill_fault.py <task-definition-json> <fault-mode>",
            file=sys.stderr,
        )
        return 2

    path = Path(sys.argv[1])
    fault_mode = sys.argv[2]
    fault_env = {
        "ROLLOUT_DRILL_FAULT_MODE": fault_mode,
        "ROLLOUT_DRILL_FAULT_PATHS": "/ready",
        "ROLLOUT_DRILL_FAULT_DELAY_SECONDS": "3",
        "ROLLOUT_DRILL_FAULT_STATUS_CODE": "503",
    }
    task_definition = _load_task_definition(path)

    for container in task_definition.get("containerDefinitions", []):
        if container.get("name") != "app":
            continue
        existing = {
            item["name"]: item["value"] for item in container.get("environment", [])
        }
        existing.update(fault_env)
        container["environment"] = [
            {"name": name, "value": value} for name, value in sorted(existing.items())
        ]
        _write_task_definition(path, task_definition)
        return 0

    print("app container not found in rendered task definition", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
