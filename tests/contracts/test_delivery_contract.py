from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_repository_does_not_track_generated_or_placeholder_artifacts() -> None:
    tracked_files = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    forbidden_segments = [
        "__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".venv/",
        ".terraform/",
        ".egg-info/",
        "/dist/",
        "/build/",
    ]
    forbidden_suffixes = [
        ".pyc",
        ".pyo",
        ".tmp",
        ".bak",
        ".swp",
        "~",
    ]

    offenders = [
        path
        for path in tracked_files
        if any(segment in f"{path}/" for segment in forbidden_segments)
        or any(path.endswith(suffix) for suffix in forbidden_suffixes)
    ]

    assert offenders == []

    placeholder_roots = [
        ROOT / "deploy",
        ROOT / "local",
        ROOT / "ops",
        ROOT / "security",
    ]

    for path in placeholder_roots:
        assert not path.exists()


def test_platform_root_stays_bootstrap_and_github_oidc_only() -> None:
    platform_tf = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra" / "platform").glob("*.tf"))
    )
    forbidden_runtime_resources = [
        'resource "aws_ecs_',
        'resource "aws_db_',
        'resource "aws_rds_',
        'resource "aws_lb"',
        'resource "aws_lb_',
        'resource "aws_ecr_',
        'resource "aws_s3_bucket"',
        'resource "aws_sqs_',
        'resource "aws_sns_',
        'resource "aws_cloudwatch_',
        'resource "aws_scheduler_',
        'resource "aws_wafv2_',
    ]

    for forbidden in forbidden_runtime_resources:
        assert forbidden not in platform_tf


def test_app_root_consumes_platform_only_through_remote_state_outputs() -> None:
    providers_tf = _read("infra/app/providers.tf")
    app_tf = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra" / "app").glob("*.tf"))
    )

    assert 'data "terraform_remote_state" "platform"' in providers_tf
    assert "platform = data.terraform_remote_state.platform.outputs" in providers_tf
    assert 'source  = "../platform"' not in app_tf
    assert "data.aws_vpc" not in app_tf
    assert "data.aws_subnets" not in app_tf


def test_terraform_state_uses_s3_native_lockfiles_only() -> None:
    versions_text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ["infra/platform/versions.tf", "infra/app/versions.tf"]
    )
    state_docs = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in [
            "Makefile",
            "docs/deployment.md",
            "infra/platform/github_actions.tf",
        ]
    )

    assert versions_text.count("use_lockfile = true") == 2
    assert "dynamodb_table" not in versions_text
    assert "terraform-locks" not in state_docs
    assert "dynamodb:" not in state_docs


def test_app_rollback_drill_enforces_pipeline_slos() -> None:
    workflow_text = _read(".github/workflows/app-rollback-drill.yml")
    workflow = yaml.safe_load(workflow_text)

    env = workflow["env"]
    assert env["APP_ROLLBACK_ERROR_SLO_SECONDS"] == "600"
    assert env["APP_ROLLBACK_LATENCY_SLO_SECONDS"] == "900"
    assert env["APP_ROLLBACK_VERIFY_SLO_SECONDS"] == "120"


def test_data_runtime_rollback_drill_enforces_pipeline_slos() -> None:
    workflow_text = _read(".github/workflows/data-runtime-rollback-drill.yml")
    workflow = yaml.safe_load(workflow_text)

    env = workflow["env"]
    assert env["DATA_RUNTIME_ROLLBACK_SLO_SECONDS"] == "120"
    assert env["DATA_RUNTIME_VERIFY_SLO_SECONDS"] == "120"

    assert "inputs.confirm_drill == 'data-rollback-drill'" in workflow_text
    assert "READ_MODE=legacy and WRITE_MODE=legacy" in workflow_text
    assert '--data \'{"mode":"dual"}\'' in workflow_text

    for forbidden in ["Run Liquibase", "Run backfill", "data export", "POST /orders"]:
        assert forbidden not in workflow_text


def test_infra_apply_guards_app_task_definition_drift() -> None:
    workflow_text = _read(".github/workflows/infra-apply.yml")
    guard_script = _read("scripts/ci/ci_guard_infra_plan_blast_radius.sh")

    assert "allow_ecs_task_definition_changes" in workflow_text
    assert "Guard reviewed plan blast radius" in workflow_text
    assert (
        "scripts/ci/ci_guard_infra_plan_blast_radius.sh infra/app/app_plan_output.txt"
        in workflow_text
    )
    assert "aws_ecs_task_definition" in guard_script
    assert "allow-ecs-task-definition-changes" in workflow_text
    assert "This can roll infra apply across the app deploy ownership boundary" in (
        guard_script
    )


def test_workflow_inventory_keeps_only_permanent_delivery_paths() -> None:
    workflow_names = {
        path.name: _read(str(path.relative_to(ROOT)))
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    }
    required = {
        "app-build.yml",
        "app-deploy.yml",
        "app-rollback-drill.yml",
        "data-runtime-rollback-drill.yml",
        "infra-apply.yml",
        "infra-plan.yml",
        "security.yml",
        "semgrep.yml",
    }
    assert required.issubset(workflow_names)

    all_workflows = "\n".join(workflow_names.values())
    assert "confirm_migration" not in all_workflows
    assert "terraform state rm" not in all_workflows
    assert "Infra App Task Definition Ownership Migration" not in all_workflows
    assert "python3 - <<'PY'" not in all_workflows
