from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
CONFIRM_INPUT_RE = re.compile(r"^confirm_[a-z0-9_]+$")


def _tracked_workflow_files(repo_root: Path = REPO_ROOT) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", ".github/workflows/*.yml", ".github/workflows/*.yaml"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [repo_root / line for line in result.stdout.splitlines() if line]


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _yaml_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or ":" not in stripped:
        return None
    return stripped.split(":", 1)[0].strip("'\"")


def _block(lines: list[str], start_index: int, parent_indent: int) -> list[str]:
    child_lines: list[str] = []
    for line in lines[start_index + 1 :]:
        if line.strip() and not line.lstrip().startswith("#") and _indent(line) <= parent_indent:
            break
        child_lines.append(line)
    return child_lines


def _list_items_from_block(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].split("#", 1)[0].strip().strip("'\"")
        if item:
            items.append(item)
    return items


def _paths_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    for index, line in enumerate(lines):
        if _yaml_key(line) == "paths":
            blocks.append(_block(lines, index, _indent(line)))
    return blocks


def _confirmation_inputs(lines: list[str]) -> list[str]:
    confirmations: list[str] = []

    for index, line in enumerate(lines):
        if _yaml_key(line) != "workflow_dispatch":
            continue

        dispatch_block = _block(lines, index, _indent(line))
        for block_index, block_line in enumerate(dispatch_block):
            input_name = _yaml_key(block_line)
            if input_name is None or CONFIRM_INPUT_RE.fullmatch(input_name) is None:
                continue

            input_block = _block(dispatch_block, block_index, _indent(block_line))
            attributes = {
                _yaml_key(attribute_line): attribute_line.split(":", 1)[1].strip().strip("'\"")
                for attribute_line in input_block
                if _yaml_key(attribute_line) is not None and ":" in attribute_line
            }
            if attributes.get("required") == "true" and attributes.get("type") == "string":
                confirmations.append(input_name)

    return confirmations


def _has_confirmation_gate(lines: list[str], input_name: str) -> bool:
    input_pattern = re.compile(rf"inputs\.{re.escape(input_name)}\s*==\s*['\"][^'\"]+['\"]")
    event_patterns = (
        "github.event_name == 'workflow_dispatch'",
        'github.event_name == "workflow_dispatch"',
    )

    return any(
        input_pattern.search(line) is not None
        and any(event_pattern in line for event_pattern in event_patterns)
        for line in lines
    )


def check_workflow(path: Path, repo_root: Path = REPO_ROOT) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel_path = path.relative_to(repo_root).as_posix()
    failures: list[str] = []

    for paths_block in _paths_blocks(lines):
        path_items = _list_items_from_block(paths_block)
        if path_items and rel_path not in path_items:
            failures.append(f"{rel_path}: every paths filter must include {rel_path}")

    if "id-token: write" in text:
        confirmation_inputs = _confirmation_inputs(lines)
        if not confirmation_inputs:
            failures.append(
                f"{rel_path}: OIDC-enabled workflows must define a required string confirm_* workflow_dispatch input"
            )
        elif not any(_has_confirmation_gate(lines, input_name) for input_name in confirmation_inputs):
            failures.append(
                f"{rel_path}: OIDC-enabled workflows must gate an AWS-changing job on workflow_dispatch and confirm_*"
            )

    return failures


def main() -> int:
    failures: list[str] = []
    for workflow in _tracked_workflow_files():
        failures.extend(check_workflow(workflow))

    if failures:
        print("GitHub workflow policy check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print("GitHub workflow policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
