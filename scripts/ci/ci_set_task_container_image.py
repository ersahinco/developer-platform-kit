#!/usr/bin/env python3
"""Set one container image in a rendered ECS task definition JSON file."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: ci_set_task_container_image.py <task-definition-json> <container-name> <image>",
            file=sys.stderr,
        )
        return 2

    path = Path(sys.argv[1])
    container_name = sys.argv[2]
    image = sys.argv[3]

    task_definition = json.loads(path.read_text(encoding="utf-8"))
    for container in task_definition.get("containerDefinitions", []):
        if container.get("name") == container_name:
            container["image"] = image
            path.write_text(
                json.dumps(task_definition, indent=2) + "\n",
                encoding="utf-8",
            )
            return 0

    print(f"container {container_name!r} not found in {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
