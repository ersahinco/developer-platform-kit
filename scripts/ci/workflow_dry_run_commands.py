from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"


@dataclass(frozen=True)
class DryRunWorkflow:
    filename: str
    inputs: tuple[tuple[str, str], ...]

    @property
    def path(self) -> Path:
        return WORKFLOW_DIR / self.filename


def env(name: str, default: str) -> str:
    return os.environ.get(name) or default


def default_image_tag() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    except OSError, subprocess.CalledProcessError:
        return "sha-<commit>"
    return f"sha-{completed.stdout.strip()}"


def dry_run_workflows() -> tuple[DryRunWorkflow, ...]:
    image_tag = env("IMAGE_TAG", default_image_tag())
    target_workload = env("TARGET_WORKLOAD", "all")
    schema_phase = env("SCHEMA_PHASE", "expand")
    switch_step = env("SWITCH_STEP", "auto-detect")
    plan_run_id = env("PLAN_RUN_ID", "<infra-plan-run-id>")

    return (
        DryRunWorkflow(
            "app-deploy.yml",
            (
                ("image_tag", image_tag),
                ("confirm_deploy", "dry-run"),
                ("dry_run", "true"),
            ),
        ),
        DryRunWorkflow(
            "data-support-deploy.yml",
            (
                ("image_tag", image_tag),
                ("target_workload", target_workload),
                ("confirm_data_support_deploy", "dry-run"),
                ("dry_run", "true"),
            ),
        ),
        DryRunWorkflow(
            "data-schema-apply.yml",
            (
                ("image_tag", image_tag),
                ("schema_phase", schema_phase),
                ("confirm_schema_apply", "dry-run"),
                ("dry_run", "true"),
            ),
        ),
        DryRunWorkflow(
            "data-runtime-switch.yml",
            (
                ("switch_step", switch_step),
                ("confirm_switch", "dry-run"),
                ("dry_run", "true"),
            ),
        ),
        DryRunWorkflow(
            "data-backfill.yml",
            (
                ("image_tag", image_tag),
                ("confirm_backfill", "dry-run"),
                ("dry_run", "true"),
            ),
        ),
        DryRunWorkflow(
            "infra-apply.yml",
            (
                ("plan_run_id", plan_run_id),
                ("confirm_apply", "dry-run"),
                ("dry_run", "true"),
            ),
        ),
    )


def dispatch_command(workflow: DryRunWorkflow) -> str:
    parts = ["gh", "workflow", "run", workflow.filename, "--ref", "main"]
    for name, value in workflow.inputs:
        parts.extend(["-f", f"{name}={value}"])
    return " ".join(shlex.quote(part) for part in parts)


def workflow_dispatch_inputs(path: Path) -> set[str]:
    lines = path.read_text().splitlines()
    in_dispatch = False
    in_inputs = False
    dispatch_indent = 0
    inputs_indent = 0
    names: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if stripped == "workflow_dispatch:":
            in_dispatch = True
            in_inputs = False
            dispatch_indent = indent
            continue
        if in_dispatch and indent <= dispatch_indent and stripped.endswith(":"):
            in_dispatch = False
            in_inputs = False
        if not in_dispatch:
            continue
        if stripped == "inputs:":
            in_inputs = True
            inputs_indent = indent
            continue
        if in_inputs and indent <= inputs_indent and stripped.endswith(":"):
            in_inputs = False
        if in_inputs and indent == inputs_indent + 2 and stripped.endswith(":"):
            names.add(stripped[:-1])
    return names


def validate_local() -> int:
    errors: list[str] = []
    for workflow in dry_run_workflows():
        path = workflow.path
        if not path.exists():
            errors.append(f"{workflow.filename} does not exist")
            continue
        declared_inputs = workflow_dispatch_inputs(path)
        used_inputs = {name for name, _value in workflow.inputs}
        missing = sorted(used_inputs - declared_inputs)
        if missing:
            errors.append(
                f"{workflow.filename} generated unknown inputs: {', '.join(missing)}"
            )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("workflow dry-run commands match local workflow_dispatch inputs")
    return 0


def print_commands() -> int:
    print("Use these after pushing the reviewed branch to the default branch.")
    print(
        "IMAGE_TAG defaults to the current commit; override it with "
        "IMAGE_TAG=sha-<commit>."
    )
    print()
    for workflow in dry_run_workflows():
        print(dispatch_command(workflow))
    return 0


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "commands"
    if command == "commands":
        return print_commands()
    if command == "validate-local":
        return validate_local()
    print(
        "usage: workflow_dry_run_commands.py [commands|validate-local]", file=sys.stderr
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
