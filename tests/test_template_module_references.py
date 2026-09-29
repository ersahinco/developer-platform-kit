"""Check module/lane references against this checkout, without fetching remote refs."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from scaffold.new_repo import template_files

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = REPO_ROOT / "modules" / "aws"
MODULE_REFERENCE = re.compile(r"//modules/aws/([a-z0-9-]+)")
LANE_REFERENCE = re.compile(r"\.github/workflows/(reusable-[a-z0-9-]+\.yml)")


TEMPLATE_FILES = template_files(REPO_ROOT / "repo-templates")


@pytest.mark.parametrize(
    "directory,reference,check",
    [
        (MODULES_DIR, MODULE_REFERENCE, Path.is_dir),
        (REPO_ROOT / ".github/workflows", LANE_REFERENCE, Path.is_file),
    ],
    ids=["modules", "lanes"],
)
def test_template_references_exist(
    directory: Path, reference: re.Pattern[str], check: Callable[[Path], bool]
) -> None:
    missing: dict[str, set[str]] = {}
    seen: set[str] = set()

    for path in TEMPLATE_FILES:
        for name in reference.findall(path.read_text()):
            seen.add(name)
            if not check(directory / name):
                missing.setdefault(str(path.relative_to(REPO_ROOT)), set()).add(name)

    assert not missing, f"Templates reference missing entries in {directory}: {missing}"
    assert seen, f"No template references {directory}."


def test_every_module_has_a_caller() -> None:
    referenced: set[str] = set()
    for path in TEMPLATE_FILES:
        referenced.update(MODULE_REFERENCE.findall(path.read_text()))

    orphans = [
        directory.name
        for directory in sorted(MODULES_DIR.iterdir())
        if directory.is_dir() and directory.name not in referenced
    ]
    assert not orphans, f"Modules with no caller in any template: {orphans}"
