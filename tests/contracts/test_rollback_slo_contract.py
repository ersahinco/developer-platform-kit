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

    assert "allow_ecs_task_definition_changes" in workflow_text
    assert "Guard reviewed plan blast radius" in workflow_text
    assert "aws_ecs_task_definition" in workflow_text
    assert "allow-ecs-task-definition-changes" in workflow_text
    assert "This can roll infra apply across the app deploy ownership boundary" in (
        workflow_text
    )


def test_rollback_slo_runbook_covers_app_infra_and_data_paths() -> None:
    runbook = _read("docs/runbooks/rollback-drill-slos.md")
    runbooks_index = _read("docs/runbooks/README.md")
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
    assert "Rollback Drill SLOs" in ecs_runbook
    assert "Rollback Drill SLOs" in infra_runbook
    assert "rollback-drill-slos.md" in deployment
