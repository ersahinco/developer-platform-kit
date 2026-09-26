"""Templates must point at modules and lanes that exist.

Renaming a module silently breaks every scaffolded infra repo the next time it
runs `terraform init`. This moves that failure to the commit that causes it.

It does not prove the sources resolve over the network: a rendered source points
at the consumer's own toolkit repository and ref, which exists only once they
have pushed it. It proves the paths inside this repository are real.
"""

from __future__ import annotations

import re
from pathlib import Path

from scaffold.new_repo import template_files

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = REPO_ROOT / "modules" / "aws"
MODULE_REFERENCE = re.compile(r"//modules/aws/(?P<module>[a-z0-9-]+)")
LANE_REFERENCE = re.compile(r"\.github/workflows/(?P<lane>reusable-[a-z0-9-]+\.yml)")


def _template_files() -> list[Path]:
    return template_files(REPO_ROOT / "repo-templates")


def test_referenced_modules_exist() -> None:
    missing: dict[str, set[str]] = {}
    seen: set[str] = set()

    for path in _template_files():
        for match in MODULE_REFERENCE.finditer(path.read_text()):
            module = match.group("module")
            seen.add(module)
            if not (MODULES_DIR / module).is_dir():
                missing.setdefault(str(path.relative_to(REPO_ROOT)), set()).add(module)

    assert not missing, f"Templates reference modules that do not exist: {missing}"
    assert seen, "No template references any module. The infra template should."


def test_referenced_lanes_exist() -> None:
    lanes_dir = REPO_ROOT / ".github" / "workflows"
    missing: dict[str, set[str]] = {}
    seen: set[str] = set()

    for path in _template_files():
        for match in LANE_REFERENCE.finditer(path.read_text()):
            lane = match.group("lane")
            seen.add(lane)
            if not (lanes_dir / lane).is_file():
                missing.setdefault(str(path.relative_to(REPO_ROOT)), set()).add(lane)

    assert not missing, f"Templates call lanes that do not exist: {missing}"
    assert seen, "No template calls a lane. Every template should."


def test_every_module_has_a_caller() -> None:
    """A module nothing calls is weight. Wire it into a template or delete it."""
    referenced: set[str] = set()
    for path in _template_files():
        referenced.update(m.group("module") for m in MODULE_REFERENCE.finditer(path.read_text()))

    orphans = [
        directory.name
        for directory in sorted(MODULES_DIR.iterdir())
        if directory.is_dir() and directory.name not in referenced
    ]
    assert not orphans, f"Modules with no caller in any template: {orphans}"
