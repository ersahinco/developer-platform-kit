#!/usr/bin/env python3
"""Strip the 'tags' key from a task-definition JSON file when its value is an empty list.

Usage:
    python3 scripts/ci/ci_strip_empty_tags.py <task-definition-json-path>

The file is modified in place. If 'tags' is absent or non-empty, the file is
written back unchanged (normalised JSON with 2-space indent and trailing newline).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def strip_empty_tags(path: Path) -> None:
    task_definition = json.loads(path.read_text(encoding="utf-8"))
    if task_definition.get("tags") == []:
        del task_definition["tags"]
    path.write_text(json.dumps(task_definition, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print(
            f"usage: {sys.argv[0]} <task-definition-json-path>",
            file=sys.stderr,
        )
        return 1
    strip_empty_tags(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
