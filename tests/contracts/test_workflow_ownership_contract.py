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
        "rollback_category": "app_image",
        "requires": [
            "--workload-id",
            "--image-tag",
            "--task-definition",
            "--rollback-category",
        ],
        "forbids": ["terraform apply"],
    },
    "data-support-deploy.yml": {
        "lane": "data-operation",
        "event_type": "data_support_deploy",
        "rollback_category": "support_task_image",
        "requires": [
            "--workload-id",
            "--image-tag",
            "--deployment-id",
            "--rollback-category",
        ],
        "forbids": ["terraform apply", "aws ecs update-service"],
    },
    "data-runtime-switch.yml": {
        "lane": "data-operation",
        "event_type": "data_runtime_switch",
        "rollback_category": "runtime_data_phase",
        "requires": ["--workload-id", "--read-mode", "--write-mode"],
        "forbids": ["terraform apply", "aws ecs register-task-definition"],
    },
    "data-schema-apply.yml": {
        "lane": "data-operation",
        "event_type": "data_schema_apply",
        "rollback_category": "schema_phase",
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
        "rollback_category": "runtime_data_phase",
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
        "rollback_category": "runtime_observability",
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

SECURITY_WORKFLOW_COMMANDS = [
    "uv sync --frozen --all-packages --group dev --group scripts --group test",
    "make secret-scan",
    "make lint-docs",
    "make lint-policy",
    "make lint-workflows",
    "make lint-dockerfiles",
    "make dependency-audit",
]

SEMGREP_PATH_FILTERS = [
    ".github/workflows/semgrep.yml",
    "apps/**",
    "packages/**",
    "scripts/**",
    "tests/**",
    "pyproject.toml",
    "uv.lock",
]
SEMGREP_SCAN_COMMAND = "semgrep scan --config auto apps/ packages/ scripts/"

MUTATING_DELIVERY_COMMANDS = [
    "aws ecs register-task-definition",
    "scripts/ci/ci_deploy_ecs_service.sh",
    "scripts/ci/ci_run_ecs_task.sh",
    "terraform apply",
    "-X POST",
]

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
        "opentofu-compatibility": {"contents": "read"},
        "plan": {"contents": "read", "id-token": "write"},
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


def _workflow_triggers(name: str) -> dict:
    workflow = _workflow_yaml(name)
    triggers = workflow.get("on", workflow.get(True, {}))
    assert isinstance(triggers, dict), name
    return triggers


def _release_event_types(text: str) -> list[str]:
    return re.findall(r"--event-type\s+([a-z_]+)", text)


def _release_event_block(text: str) -> str:
    marker = "python3 -m scripts.observability.release_event"
    if marker not in text:
        return ""
    return text[text.index(marker) :]


def _workflow_dispatch_inputs(name: str) -> dict:
    return _workflow_triggers(name).get("workflow_dispatch", {}).get("inputs", {})


def _job_text(job: dict) -> str:
    return yaml.safe_dump(job, sort_keys=True)


def _step_env(step: dict) -> dict:
    env = step.get("env", {})
    return env if isinstance(env, dict) else {}


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


def test_infra_plan_uses_default_branch_oidc_identity() -> None:
    workflow = _workflow_yaml("infra-plan.yml")
    plan = workflow["jobs"]["plan"]
    credentials_step = next(
        step
        for step in plan["steps"]
        if step.get("uses", "").startswith("aws-actions/configure-aws-credentials@")
    )

    assert "github.event_name != 'pull_request'" in plan["if"]
    assert "github.ref_name == github.event.repository.default_branch" in plan["if"]
    assert "environment" not in plan
    assert credentials_step["with"]["role-to-assume"] == "${{ vars.AWS_ROLE_ARN }}"
    assert all(step.get("name") != "Post plan to PR" for step in plan["steps"])


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
        rollback_category = expected.get("rollback_category")
        if rollback_category is not None:
            assert f"--rollback-category {rollback_category}" in release_block, (
                f"{workflow_name} missing rollback category {rollback_category}"
            )


def test_workflow_lanes_do_not_pick_up_other_cloud_changing_responsibilities() -> None:
    for workflow_name, expected in WORKFLOW_OWNERSHIP.items():
        text = _workflow_text(workflow_name)
        for forbidden in expected["forbids"]:
            assert forbidden not in text, f"{workflow_name} must not run {forbidden}"


def test_image_tag_inputs_are_validated_before_cloud_changing_work() -> None:
    for workflow_name in WORKFLOW_OWNERSHIP:
        inputs = _workflow_dispatch_inputs(workflow_name)
        if "image_tag" not in inputs:
            continue

        text = _workflow_text(workflow_name)
        assert "scripts/ci/ci_validate_image_tag.sh" in text, workflow_name


def test_dry_run_workflows_guard_runtime_mutation_steps() -> None:
    for workflow_name in WORKFLOW_OWNERSHIP:
        if "dry_run" not in _workflow_dispatch_inputs(workflow_name):
            continue

        workflow = _workflow_yaml(workflow_name)
        for job_name, job in workflow["jobs"].items():
            for step in job.get("steps", []):
                run = str(step.get("run", ""))
                if not any(command in run for command in MUTATING_DELIVERY_COMMANDS):
                    continue

                assert _step_is_guarded_from_dry_run(job, step), (
                    workflow_name,
                    job_name,
                    step.get("name"),
                )


def test_dry_run_workflows_do_not_emit_release_evidence() -> None:
    for workflow_name in WORKFLOW_OWNERSHIP:
        workflow = _workflow_yaml(workflow_name)
        inputs = _workflow_dispatch_inputs(workflow_name)
        for job_name, job in workflow["jobs"].items():
            if "scripts.observability.release_event" not in _job_text(job):
                continue
            job_if = str(job.get("if", ""))
            if "dry_run" in inputs:
                assert "!inputs.dry_run" in job_if, (workflow_name, job_name)
            else:
                assert "inputs.confirm_build == 'build'" in job_if, (
                    workflow_name,
                    job_name,
                )


def test_security_workflow_runs_repo_hygiene_gates_with_standard_tools() -> None:
    workflow = _workflow_yaml("security.yml")
    steps = workflow["jobs"]["security-scan"]["steps"]
    run_commands = [step["run"] for step in steps if "run" in step]

    assert run_commands == SECURITY_WORKFLOW_COMMANDS


def test_semgrep_workflow_scans_owned_code_paths_with_pinned_container() -> None:
    workflow = _workflow_yaml("semgrep.yml")
    triggers = _workflow_triggers("semgrep.yml")
    job = workflow["jobs"]["scan"]

    assert triggers["pull_request"]["paths"] == SEMGREP_PATH_FILTERS
    assert triggers["push"]["paths"] == SEMGREP_PATH_FILTERS
    assert re.match(
        r"semgrep/semgrep:[^@]+@sha256:[0-9a-f]{64}$",
        job["container"]["image"],
    )
    assert job["steps"][-1]["run"] == SEMGREP_SCAN_COMMAND


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


def test_app_deploy_emits_app_host_set_evidence() -> None:
    text = _workflow_text("app-deploy.yml")

    assert "app_host_workloads" in text
    assert "steps.internal-services.outputs.internal_workloads" in text
    assert 'related_workload_args+=(--related-workload-id "$workload_id")' in text
    assert '"${related_workload_args[@]}"' in text


def test_app_build_uploads_monorepo_capability_profile_artifact() -> None:
    text = _workflow_text("app-build.yml")

    assert "infra/catalog/**" in text
    assert "make monorepo-capability-profile-check" in text
    assert "make monorepo-capability-profile-md" in text
    assert "monorepo-capability-profile-${{ github.run_id }}" in text
    assert "profile.json" in text
    assert "profile.md" in text


def test_data_support_deploy_emits_targeted_workload_evidence() -> None:
    text = _workflow_text("data-support-deploy.yml")

    assert 'evidence_workload_id="${{ inputs.target_workload }}"' in text
    assert 'if [[ "$evidence_workload_id" == "all" ]]' in text
    assert '--workload-id "$evidence_workload_id"' in text
