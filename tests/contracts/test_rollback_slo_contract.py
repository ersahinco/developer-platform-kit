from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_app_rollback_drill_enforces_pipeline_slos() -> None:
    workflow_text = _read(".github/workflows/app-rollback-drill.yml")
    workflow = yaml.safe_load(workflow_text)

    env = workflow["env"]
    assert env["APP_ROLLBACK_ERROR_SLO_SECONDS"] == "600"
    assert env["APP_ROLLBACK_LATENCY_SLO_SECONDS"] == "900"
    assert env["APP_ROLLBACK_VERIFY_SLO_SECONDS"] == "120"

    assert "deploy_started_epoch=$(date +%s)" in workflow_text
    assert "rollback_seconds=$(($(date +%s) - DEPLOY_STARTED_EPOCH))" in (workflow_text)
    assert "ECS rollback exceeded ${FAULT_MODE} SLO" in workflow_text
    assert "Restored app verification exceeded SLO" in workflow_text
    assert "Rollback drill SLO evidence" in workflow_text


def test_data_runtime_rollback_drill_enforces_pipeline_slos() -> None:
    workflow_text = _read(".github/workflows/data-runtime-rollback-drill.yml")
    workflow = yaml.safe_load(workflow_text)

    env = workflow["env"]
    assert env["DATA_RUNTIME_ROLLBACK_SLO_SECONDS"] == "120"
    assert env["DATA_RUNTIME_VERIFY_SLO_SECONDS"] == "120"

    assert "inputs.confirm_drill == 'data-rollback-drill'" in workflow_text
    assert "READ_MODE=legacy and WRITE_MODE=legacy" in workflow_text
    assert '--data \'{"mode":"dual"}\'' in workflow_text
    assert (
        "PREVIOUS_WRITE_MODE: ${{ steps.current.outputs.write_mode }}" in workflow_text
    )
    assert "Restore captured write mode if needed" in workflow_text
    assert "Runtime config rollback SLO evidence" in workflow_text
    assert "Restored runtime verification exceeded SLO" in workflow_text

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


def test_app_task_definition_ownership_migration_is_reviewed_and_guarded() -> None:
    workflow_text = _read(
        ".github/workflows/infra-app-task-definition-ownership-migration.yml"
    )

    assert "workflow_dispatch" in workflow_text
    assert "confirm_migration == 'app-task-definition-ownership'" in workflow_text
    assert "environment: aws" in workflow_text
    assert "group: infra-apply-aws" in workflow_text
    assert (
        'module.ecs.module.service["app"].aws_ecs_task_definition.this[0]'
        in workflow_text
    )
    assert "terraform state rm" in workflow_text
    assert "Verify app service is stable" in workflow_text
    assert "ci_guard_infra_plan_blast_radius.sh" in workflow_text
    assert "set -o pipefail" in workflow_text
    assert (
        "grep -Eq '^[[:space:]]*family[[:space:]]*=[[:space:]]*\"aws-sdlc-containers\"'"
        in workflow_text
    )
    assert "terraform apply -auto-approve app-task-definition-ownership.tfplan" in (
        workflow_text
    )


def test_workflow_inventory_keeps_drills_and_migrations_separate() -> None:
    workflow_names = {
        path.name: _read(str(path.relative_to(ROOT)))
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    }
    rollback_drills = [
        name
        for name, text in workflow_names.items()
        if "Rollback Drill" in text.splitlines()[0]
    ]

    assert sorted(rollback_drills) == [
        "app-rollback-drill.yml",
        "data-runtime-rollback-drill.yml",
    ]
    assert "Infra Plan" in workflow_names["infra-plan.yml"].splitlines()[0]
    assert "Infra Apply" in workflow_names["infra-apply.yml"].splitlines()[0]
    assert (
        "Rollback Drill"
        not in workflow_names[
            "infra-app-task-definition-ownership-migration.yml"
        ].splitlines()[0]
    )
    assert (
        "confirm_migration"
        in workflow_names["infra-app-task-definition-ownership-migration.yml"]
    )


def test_rollback_slo_runbook_covers_app_infra_and_data_paths() -> None:
    runbook = _read("docs/runbooks/rollback-drill-slos.md")
    runbooks_index = _read("docs/runbooks/README.md")
    ownership_runbook = _read("docs/runbooks/app-infra-ownership.md")
    ecs_runbook = _read("docs/runbooks/ecs-deploy-rollback.md")
    infra_runbook = _read("docs/runbooks/infra-rollback-drill.md")
    deployment = _read("docs/deployment.md")

    for phrase in [
        "App rollback, error mode",
        "App rollback, latency mode",
        "Infra no-data rollback",
        "Runtime data-phase rollback",
        "Data Runtime Rollback Drill",
        "Infra Drill Preflight",
        "Backfill/data job containment",
        "25627263917",
        "25627680472",
        "25675925524",
        "25676047073",
    ]:
        assert phrase in runbook

    assert "rollback-drill-slos.md" in runbooks_index
    assert "app-infra-ownership.md" in runbooks_index
    assert "GitHub Actions owns app task-definition revisions" in ownership_runbook
    assert "ci_guard_infra_plan_blast_radius.sh" in ownership_runbook
    assert "Rollback Drill SLOs" in ecs_runbook
    assert "Rollback Drill SLOs" in infra_runbook
    assert "App And Infra Ownership Boundary" in infra_runbook
    assert "App And Infra Ownership Boundary" in deployment
    assert "rollback-drill-slos.md" in deployment
    assert "Workflow Inventory" in runbook
    assert "state migration workflows" in runbook
