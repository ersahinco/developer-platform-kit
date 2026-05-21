from __future__ import annotations

from ._helpers import (
    load_workflow,
    read_text,
    step_names,
    step_run_text,
    workflow_job,
)


def test_app_build_workflow_has_structured_build_promotion_gates() -> None:
    workflow = load_workflow(".github/workflows/app-build.yml")

    assert workflow["name"] == "App Build"
    assert {"workflow_dispatch", "pull_request", "push"} <= set(workflow["on"])

    dispatch_inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert set(dispatch_inputs) == {"confirm_build"}
    assert dispatch_inputs["confirm_build"]["required"] == "true"

    validate_job = workflow_job(workflow, "validate-and-test")
    image_matrix_job = workflow_job(workflow, "image-matrix")
    build_job = workflow_job(workflow, "build-scan-push")

    assert validate_job["permissions"]["contents"] == "read"
    assert image_matrix_job["outputs"]["images"] == "${{ steps.images.outputs.images }}"
    assert build_job["environment"] == "aws"
    assert build_job["permissions"]["id-token"] == "write"
    assert build_job["permissions"]["attestations"] == "write"

    assert {
        "Install dependencies",
        "Run Python static checks",
        "Check shell script syntax",
        "Run tests",
        "Run runtime conformance",
    } <= set(step_names(validate_job))
    assert {
        "Build image",
        "Scan image",
        "Push image",
        "Attest image provenance",
        "Upload build evidence",
    } <= set(step_names(build_job))
    assert "python3 scripts/observability/release_event.py" in step_run_text(build_job)


def test_app_deploy_and_infra_apply_keep_review_boundary_split() -> None:
    deploy_workflow = load_workflow(".github/workflows/app-deploy.yml")
    infra_apply_workflow = load_workflow(".github/workflows/infra-apply.yml")

    deploy_inputs = deploy_workflow["on"]["workflow_dispatch"]["inputs"]
    assert {"image_tag", "confirm_deploy"} <= set(deploy_inputs)

    migrate_job = workflow_job(deploy_workflow, "migrate")
    deploy_job = workflow_job(deploy_workflow, "deploy")
    deploy_evidence_job = workflow_job(deploy_workflow, "evidence")

    assert deploy_job["environment"] == "aws"
    assert {
        "Validate image tag",
        "Deploy primary edge service",
        "Verify deployed edge service",
        "Register support task definitions",
        "Deploy service task definitions",
        "Run backfill worker",
    } <= set(step_names(deploy_job))
    assert "Run Liquibase" in step_names(migrate_job)
    assert "Upload app deploy evidence" in step_names(deploy_evidence_job)

    deploy_runs = "\n".join(
        [
            step_run_text(migrate_job),
            step_run_text(deploy_job),
            step_run_text(deploy_evidence_job),
        ]
    )
    assert "terraform apply -auto-approve" not in deploy_runs
    assert "ci_deploy_ecs_service.sh" in deploy_runs
    assert "ci_run_ecs_task.sh" in deploy_runs

    apply_inputs = infra_apply_workflow["on"]["workflow_dispatch"]["inputs"]
    assert {
        "plan_run_id",
        "confirm_apply",
        "allow_ecs_task_definition_changes",
    } <= set(apply_inputs)

    apply_job = workflow_job(infra_apply_workflow, "apply")
    apply_evidence_job = workflow_job(infra_apply_workflow, "evidence")

    assert apply_job["environment"] == "aws"
    assert {
        "Resolve plan run",
        "Guard reviewed plan blast radius",
        "terraform apply platform reviewed plan",
        "terraform apply app reviewed plan",
    } <= set(step_names(apply_job))
    assert "Upload infra apply evidence" in step_names(apply_evidence_job)

    apply_runs = "\n".join(
        [step_run_text(apply_job), step_run_text(apply_evidence_job)]
    )
    assert "terraform apply -auto-approve" in apply_runs
    assert "ci_deploy_ecs_service.sh" not in apply_runs
    assert "ci_run_ecs_task.sh" not in apply_runs


def test_security_and_semgrep_workflows_own_repo_hygiene_gates() -> None:
    security_workflow = load_workflow(".github/workflows/security.yml")
    semgrep_workflow = load_workflow(".github/workflows/semgrep.yml")

    security_job = workflow_job(security_workflow, "security-scan")
    semgrep_job = workflow_job(semgrep_workflow, "scan")

    assert {
        "Run secret scan",
        "Check Markdown links",
        "Run policy checks",
        "Lint GitHub workflows",
        "Lint Dockerfiles",
        "Run Python dependency audit",
    } <= set(step_names(security_job))
    assert (
        "semgrep/semgrep:1.161.0@sha256:326e5f41cc972bb423b764a14febbb62bbad29ee1c01820805d077dd868fea48"
        == semgrep_job["container"]["image"]
    )
    assert "Run Semgrep Community Edition" in step_names(semgrep_job)
    assert "semgrep scan --config auto apps/ packages/ scripts/" in step_run_text(
        semgrep_job
    )


def test_policy_concern_is_wired_into_standard_tooling() -> None:
    makefile = read_text("Makefile")
    security_workflow = load_workflow(".github/workflows/security.yml")

    assert "lint-policy:" in makefile
    assert "conftest test --policy platform/concerns/policy/conftest" in makefile
    assert "platform/workloads.json" in makefile
    assert "platform/runtime-conformance.json" in makefile
    assert "platform/platform-inventory.json" in makefile
    assert "Run policy checks" in step_names(
        workflow_job(security_workflow, "security-scan")
    )
    assert "make lint-policy" in step_run_text(
        workflow_job(security_workflow, "security-scan")
    )
