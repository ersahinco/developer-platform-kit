from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAKE_TARGET_PATTERN = re.compile(
    r"^\s*(?:[A-Z0-9_]+=(?:\S+)\s+)*make\s+([a-zA-Z0-9_-]+)\b",
    re.MULTILINE,
)
MAKEFILE_TARGET_PATTERN = re.compile(r"^([a-zA-Z0-9_-]+):", re.MULTILINE)


def test_documented_make_targets_exist() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    declared_targets = set(MAKEFILE_TARGET_PATTERN.findall(makefile))
    markdown_paths = [
        ROOT / "README.md",
        *sorted((ROOT / "docs").rglob("*.md")),
    ]

    referenced_targets: dict[str, list[str]] = {}
    for path in markdown_paths:
        text = path.read_text(encoding="utf-8")
        for match in MAKE_TARGET_PATTERN.finditer(text):
            target = match.group(1)
            referenced_targets.setdefault(target, []).append(
                str(path.relative_to(ROOT))
            )

    missing = {
        target: paths
        for target, paths in referenced_targets.items()
        if target not in declared_targets
    }

    assert missing == {}
