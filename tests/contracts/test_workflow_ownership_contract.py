from __future__ import annotations

import re
from pathlib import Path

import yaml


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
    "local-kubernetes-contracts.yml",
    "security.yml",
    "semgrep.yml",
}

OPERATOR_PAYLOAD_CORRELATION_INPUTS = {
    "data-backfill.yml": {
        "--workload-id",
        "--image-tag",
        "--task-definition",
        "--task-arn",
    },
    "operational-snapshot.yml": {
        "--workload-id",
        "--image-tag",
        "--task-definition",
        "--task-arn",
    },
}

EXPECTED_JOB_PERMISSIONS = {
    "app-build.yml": {
        "validate-and-test": {"contents": "read"},
        "image-matrix": {"contents": "read"},
        "build-scan-push": {
            "attestations": "write",
            "contents": "read",
            "id-token": "write",
        },
    },
    "app-deploy.yml": {
        "deploy": {"contents": "read", "id-token": "write"},
        "evidence": {"contents": "read", "id-token": "write"},
    },
    "data-support-deploy.yml": {
        "deploy_support": {"contents": "read", "id-token": "write"},
        "evidence": {"contents": "read", "id-token": "write"},
    },
    "data-runtime-switch.yml": {
        "switch_runtime": {"contents": "read", "id-token": "write"},
        "evidence": {"contents": "read", "id-token": "write"},
    },
    "data-schema-apply.yml": {
        "apply_schema": {"contents": "read", "id-token": "write"},
        "evidence": {"contents": "read", "id-token": "write"},
    },
    "data-backfill.yml": {
        "run_backfill": {"contents": "read", "id-token": "write"},
        "evidence": {"contents": "read", "id-token": "write"},
    },
    "operational-snapshot.yml": {
        "run_operational_snapshot": {"contents": "read", "id-token": "write"},
        "evidence": {"contents": "read", "id-token": "write"},
    },
    "infra-plan.yml": {
        "lint-and-validate": {"contents": "read"},
        "plan": {"contents": "read", "id-token": "write", "pull-requests": "write"},
    },
    "infra-apply.yml": {
        "apply": {"actions": "read", "contents": "read", "id-token": "write"},
        "evidence": {"contents": "read", "id-token": "write"},
    },
    "local-kubernetes-contracts.yml": {"static-contracts": {"contents": "read"}},
    "security.yml": {"security-scan": {"contents": "read"}},
    "semgrep.yml": {"scan": {"contents": "read"}},
}


def _workflow_text(name: str) -> str:
    return (WORKFLOW_DIR / name).read_text(encoding="utf-8")


def _workflow_yaml(name: str) -> dict:
    return yaml.safe_load(_workflow_text(name))


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
    assert workflow_names == set(EXPECTED_JOB_PERMISSIONS)


def test_workflow_jobs_have_explicit_least_privilege_permissions() -> None:
    for workflow_name, expected_jobs in EXPECTED_JOB_PERMISSIONS.items():
        workflow = _workflow_yaml(workflow_name)

        assert workflow.get("permissions") == {"contents": "read"}
        assert set(workflow["jobs"]) == set(expected_jobs)
        for job_name, expected_permissions in expected_jobs.items():
            actual_permissions = workflow["jobs"][job_name].get("permissions")
            assert actual_permissions == expected_permissions, (
                workflow_name,
                job_name,
            )


def test_workflow_actions_are_pinned_by_full_commit_sha() -> None:
    for workflow_path in sorted(WORKFLOW_DIR.glob("*.yml")):
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

        for job_name, job in workflow["jobs"].items():
            for step in job.get("steps", []):
                uses = step.get("uses")
                if uses is None:
                    continue
                assert re.search(r"@[0-9a-f]{40}$", uses), (
                    workflow_path.name,
                    job_name,
                    uses,
                )


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


def test_operator_payloads_embed_runtime_correlation_inputs() -> None:
    for workflow_name, expected_inputs in OPERATOR_PAYLOAD_CORRELATION_INPUTS.items():
        text = _workflow_text(workflow_name)
        assert "scripts/ci/extract_operator_event.py" in text
        for expected_input in expected_inputs:
            assert expected_input in text, f"{workflow_name} missing {expected_input}"
