from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
MUTATING_DELIVERY_COMMANDS = (
    "aws ecs register-task-definition",
    "scripts/ci/ci_deploy_ecs_service.sh",
    "scripts/ci/ci_run_ecs_task.sh",
    "terraform apply",
    "-X POST",
)


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
    return "sha-<built-image-commit>"


def dry_run_workflows() -> tuple[DryRunWorkflow, ...]:
    image_tag = env("IMAGE_TAG", default_image_tag())
    target_workload = env("TARGET_WORKLOAD", "all")
    schema_phase = env("SCHEMA_PHASE", "expand")
    switch_step = env("SWITCH_STEP", "auto-detect")
    plan_run_id = env("PLAN_RUN_ID", "<infra-plan-run-id>")

    return (
        DryRunWorkflow(
            "app-build.yml",
            (("confirm_build", "dry-run"),),
        ),
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
            "operational-snapshot.yml",
            (
                ("confirm_snapshot", "dry-run"),
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


def workflow_document(path: Path) -> dict:
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(workflow, dict):
        return {}
    return workflow


def workflow_dispatch_inputs(path: Path) -> set[str]:
    workflow = workflow_document(path)
    if not workflow:
        return set()
    triggers = workflow.get("on", {})
    if not isinstance(triggers, dict):
        return set()
    dispatch = triggers.get("workflow_dispatch", {})
    if not isinstance(dispatch, dict):
        return set()
    inputs = dispatch.get("inputs", {})
    if not isinstance(inputs, dict):
        return set()
    return {str(name) for name in inputs}


def release_evidence_workflows() -> tuple[str, ...]:
    return tuple(
        path.name
        for path in sorted(WORKFLOW_DIR.glob("*.yml"))
        if "scripts.observability.release_event" in path.read_text(encoding="utf-8")
    )


def generated_dry_run_workflow_names() -> tuple[str, ...]:
    return tuple(workflow.filename for workflow in dry_run_workflows())


def _has_generated_dry_run_switch(workflow: DryRunWorkflow) -> bool:
    inputs = dict(workflow.inputs)
    if workflow.filename == "app-build.yml":
        return inputs.get("confirm_build") == "dry-run"
    return inputs.get("dry_run") == "true"


def _step_env(step: dict) -> dict:
    env = step.get("env", {})
    return env if isinstance(env, dict) else {}


def _job_text(job: dict) -> str:
    return yaml.safe_dump(job, sort_keys=True)


def _step_is_guarded_from_dry_run(job: dict, step: dict) -> bool:
    job_if = str(job.get("if", ""))
    step_if = str(step.get("if", ""))
    run = str(step.get("run", ""))
    env = _step_env(step)
    script_guard = (
        env.get("DRY_RUN") == "${{ inputs.dry_run }}"
        and 'if [[ "$DRY_RUN" != "true" ]]' in run
    )
    return "!inputs.dry_run" in job_if or "!inputs.dry_run" in step_if or script_guard


def dry_run_guard_errors(path: Path) -> list[str]:
    workflow = workflow_document(path)
    inputs = workflow_dispatch_inputs(path)
    jobs = workflow.get("jobs", {}) if isinstance(workflow.get("jobs"), dict) else {}
    errors: list[str] = []

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        job_if = str(job.get("if", ""))
        if "scripts.observability.release_event" in _job_text(job):
            if "dry_run" in inputs and "!inputs.dry_run" not in job_if:
                errors.append(
                    f"{path.name}:{job_name} emits release evidence in dry run"
                )
            if (
                "dry_run" not in inputs
                and "inputs.confirm_build == 'build'" not in job_if
            ):
                errors.append(
                    f"{path.name}:{job_name} emits release evidence without build confirmation"
                )
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            run = str(step.get("run", ""))
            if not any(command in run for command in MUTATING_DELIVERY_COMMANDS):
                continue
            if "dry_run" in inputs and not _step_is_guarded_from_dry_run(job, step):
                step_name = step.get("name") or "<unnamed>"
                errors.append(
                    f"{path.name}:{job_name}:{step_name} mutates runtime state in dry run"
                )
    return errors


def validate_local() -> int:
    errors: list[str] = []
    evidence_workflows = set(release_evidence_workflows())
    generated_workflows = set(generated_dry_run_workflow_names())
    missing_dry_run_workflows = sorted(evidence_workflows - generated_workflows)
    stale_dry_run_workflows = sorted(generated_workflows - evidence_workflows)
    if missing_dry_run_workflows:
        errors.append(
            "release-evidence workflows without generated dry-run commands: "
            + ", ".join(missing_dry_run_workflows)
        )
    if stale_dry_run_workflows:
        errors.append(
            "generated dry-run commands without release-evidence workflows: "
            + ", ".join(stale_dry_run_workflows)
        )
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
        if not _has_generated_dry_run_switch(workflow):
            errors.append(f"{workflow.filename} generated command is not a dry run")
        if workflow.filename != "app-build.yml" and "dry_run" not in declared_inputs:
            errors.append(f"{workflow.filename} does not declare dry_run input")
        errors.extend(dry_run_guard_errors(path))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(
        "workflow dry-run commands match release-evidence workflows "
        "and local workflow_dispatch inputs with non-mutating guards"
    )
    return 0


def print_commands() -> int:
    print("Use these after pushing the reviewed branch to the default branch.")
    print(
        "Set IMAGE_TAG to an immutable image tag from a successful app-build run, "
        "for example IMAGE_TAG=sha-<commit>."
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
