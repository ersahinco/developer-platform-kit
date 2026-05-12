#!/usr/bin/env python3
"""Prepare the rendered Liquibase ECS task definition for app deploy."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

LIQUIBASE_COMMAND = [
    "--search-path=/liquibase",
    "--changelog-file=changelog/db.changelog-master.yaml",
    "update",
]


def _load_task_definition(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_task_definition(path: Path, task_definition: dict[str, Any]) -> None:
    path.write_text(json.dumps(task_definition, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: ci_prepare_liquibase_task_definition.py <task-definition-json> <firelens-image>",
            file=sys.stderr,
        )
        return 2

    path = Path(sys.argv[1])
    firelens_image = sys.argv[2]
    task_definition = _load_task_definition(path)

    found_liquibase = False
    found_log_router = False
    for container in task_definition.get("containerDefinitions", []):
        if container.get("name") == "liquibase":
            container["workingDirectory"] = "/liquibase"
            container["command"] = LIQUIBASE_COMMAND
            found_liquibase = True
        if container.get("name") == "log-router":
            container["image"] = firelens_image
            found_log_router = True

    if not found_log_router:
        print(
            "log-router container not found in rendered task definition",
            file=sys.stderr,
        )
        return 1
    if not found_liquibase:
        print(
            "liquibase container not found in rendered task definition", file=sys.stderr
        )
        return 1

    _write_task_definition(path, task_definition)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
