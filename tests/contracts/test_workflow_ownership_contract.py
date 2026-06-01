from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"


WORKFLOW_OWNERSHIP = {
    "app-build.yml": {
        "lane": "build",
        "event_type": "app_build",
        "requires": [
            "--workload-id",
            "--image-tag",
            "--image-digest",
            "--deployment-id",
        ],
        "forbids": ["terraform apply", "aws ecs update-service"],
    },
    "app-deploy.yml": {
        "lane": "deploy",
        "event_type": "app_deploy",
        "requires": ["--workload-id", "--image-tag", "--task-definition"],
        "forbids": ["terraform apply"],
    },
    "data-support-deploy.yml": {
        "lane": "data-operation",
        "event_type": "data_support_deploy",
        "requires": ["--workload-id", "--image-tag", "--deployment-id"],
        "forbids": ["terraform apply", "aws ecs update-service"],
    },
    "data-runtime-switch.yml": {
        "lane": "data-operation",
        "event_type": "data_runtime_switch",
        "requires": ["--workload-id", "--read-mode", "--write-mode"],
        "forbids": ["terraform apply", "aws ecs register-task-definition"],
    },
    "data-schema-apply.yml": {
        "lane": "data-operation",
        "event_type": "data_schema_apply",
        "requires": [
            "--workload-id",
            "--image-tag",
            "--task-definition",
            "--deployment-id",
            "--read-mode",
            "--write-mode",
        ],
        "forbids": ["terraform apply", "aws ecs update-service"],
    },
    "data-backfill.yml": {
        "lane": "data-operation",
        "event_type": "data_backfill",
        "requires": [
            "--workload-id",
            "--image-tag",
            "--task-definition",
            "--deployment-id",
            "--read-mode",
            "--write-mode",
        ],
        "forbids": ["terraform apply", "aws ecs update-service"],
    },
    "operational-snapshot.yml": {
        "lane": "operator-job",
        "event_type": "operational_snapshot",
        "requires": [
            "--workload-id",
            "--image-tag",
            "--task-definition",
            "--deployment-id",
        ],
        "forbids": ["terraform apply", "aws ecs update-service"],
    },
    "infra-apply.yml": {
        "lane": "infra-apply",
        "event_type": "infra_apply",
        "requires": ["--workload-id", "--plan-run-id"],
        "forbids": ["aws ecs update-service", "aws ecs register-task-definition"],
    },
}

NON_CLOUD_CHANGING_WORKFLOWS = {
    "infra-plan.yml",
    "security.yml",
    "semgrep.yml",
}


def _workflow_text(name: str) -> str:
    return (WORKFLOW_DIR / name).read_text(encoding="utf-8")


def _release_event_types(text: str) -> list[str]:
    return re.findall(r"--event-type\s+([a-z_]+)", text)


def _release_event_block(text: str) -> str:
    marker = "python3 -m scripts.observability.release_event"
    if marker not in text:
        return ""
    return text[text.index(marker) :]


def test_all_workflows_have_one_documented_ownership_lane() -> None:
    workflow_names = {path.name for path in WORKFLOW_DIR.glob("*.yml")}

    assert workflow_names == set(WORKFLOW_OWNERSHIP) | NON_CLOUD_CHANGING_WORKFLOWS


def test_cloud_changing_workflows_emit_one_release_event_with_correlation_inputs() -> (
    None
):
    for workflow_name, expected in WORKFLOW_OWNERSHIP.items():
        text = _workflow_text(workflow_name)
        event_types = _release_event_types(text)

        assert event_types == [expected["event_type"]], workflow_name

        release_block = _release_event_block(text)
        for required in expected["requires"]:
            assert required in release_block, f"{workflow_name} missing {required}"


def test_workflow_lanes_do_not_pick_up_other_cloud_changing_responsibilities() -> None:
    for workflow_name, expected in WORKFLOW_OWNERSHIP.items():
        text = _workflow_text(workflow_name)
        for forbidden in expected["forbids"]:
            assert forbidden not in text, f"{workflow_name} must not run {forbidden}"


def test_non_cloud_changing_workflows_do_not_emit_release_evidence() -> None:
    for workflow_name in NON_CLOUD_CHANGING_WORKFLOWS:
        text = _workflow_text(workflow_name)
        assert "scripts.observability.release_event" not in text
        assert "release-evidence-" not in text
