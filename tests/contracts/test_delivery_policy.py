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
    assert "examples/**" not in workflow["on"]["pull_request"]["paths"]
    assert "examples/**" not in workflow["on"]["push"]["paths"]

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
    assert "uv run ruff format --check apps/ packages/ tests/ scripts/" in (
        step_run_text(validate_job)
    )
    assert "uv run ruff check apps/ packages/ tests/ scripts/" in (
        step_run_text(validate_job)
    )
    assert "examples/" not in step_run_text(validate_job)
    assert {
        "Build image",
        "Scan image",
        "Check existing immutable image tag",
        "Push image",
        "Attest image provenance",
        "Upload build evidence",
    } <= set(step_names(build_job))
    assert "python3 -m scripts.observability.release_event" in step_run_text(build_job)
    assert "aws ecr describe-images" in step_run_text(build_job)


def test_app_deploy_data_workflows_and_infra_apply_keep_review_boundary_split() -> None:
    deploy_workflow = load_workflow(".github/workflows/app-deploy.yml")
    data_support_workflow = load_workflow(".github/workflows/data-support-deploy.yml")
    data_runtime_switch_workflow = load_workflow(
        ".github/workflows/data-runtime-switch.yml"
    )
    data_schema_workflow = load_workflow(".github/workflows/data-schema-apply.yml")
    data_backfill_workflow = load_workflow(".github/workflows/data-backfill.yml")
    infra_apply_workflow = load_workflow(".github/workflows/infra-apply.yml")
    infra_plan_workflow = load_workflow(".github/workflows/infra-plan.yml")

    deploy_inputs = deploy_workflow["on"]["workflow_dispatch"]["inputs"]
    assert {"image_tag", "confirm_deploy"} <= set(deploy_inputs)

    deploy_job = workflow_job(deploy_workflow, "deploy")
    deploy_evidence_job = workflow_job(deploy_workflow, "evidence")

    assert deploy_job["environment"] == "aws"
    assert {
        "Resolve root domain",
        "Validate image tag",
        "Deploy primary edge service",
        "Deploy service task definitions",
        "Verify deployed edge service",
    } <= set(step_names(deploy_job))
    assert "Upload app deploy evidence" in step_names(deploy_evidence_job)

    deploy_runs = "\n".join(
        [step_run_text(deploy_job), step_run_text(deploy_evidence_job)]
    )
    assert "terraform apply -auto-approve" not in deploy_runs
    assert "ci_deploy_ecs_service.sh" in deploy_runs
    assert "ci_run_ecs_task.sh" not in deploy_runs
    assert "Run Liquibase" not in step_names(deploy_job)
    assert "Run backfill worker" not in step_names(deploy_job)

    data_support_inputs = data_support_workflow["on"]["workflow_dispatch"]["inputs"]
    assert {
        "image_tag",
        "target_workload",
        "confirm_data_support_deploy",
    } <= set(data_support_inputs)

    data_support_job = workflow_job(data_support_workflow, "deploy_support")
    data_support_evidence_job = workflow_job(data_support_workflow, "evidence")

    assert data_support_job["environment"] == "aws"
    assert {"Validate image tag", "Register support task definitions"} <= set(
        step_names(data_support_job)
    )
    assert "Upload data support deploy evidence" in step_names(
        data_support_evidence_job
    )
    data_support_runs = "\n".join(
        [step_run_text(data_support_job), step_run_text(data_support_evidence_job)]
    )
    assert "ci_deploy_ecs_service.sh" not in data_support_runs
    assert "ci_run_ecs_task.sh" not in data_support_runs
    assert "aws ecs register-task-definition" in data_support_runs
    assert "inputs.target_workload" in data_support_runs
    assert "Unsupported target_workload" in data_support_runs

    data_runtime_switch_inputs = data_runtime_switch_workflow["on"][
        "workflow_dispatch"
    ]["inputs"]
    assert {"switch_step", "confirm_switch"} <= set(data_runtime_switch_inputs)

    data_runtime_switch_job = workflow_job(
        data_runtime_switch_workflow, "switch_runtime"
    )
    data_runtime_switch_evidence_job = workflow_job(
        data_runtime_switch_workflow, "evidence"
    )

    assert data_runtime_switch_job["environment"] == "aws"
    assert {
        "Resolve root domain",
        "Require stable primary edge service",
        "Resolve reviewed transition",
        "Capture current runtime modes",
        "Apply runtime switch",
        "Verify switched runtime modes",
    } <= set(step_names(data_runtime_switch_job))
    assert "Upload data runtime switch evidence" in step_names(
        data_runtime_switch_evidence_job
    )
    data_runtime_switch_runs = "\n".join(
        [
            step_run_text(data_runtime_switch_job),
            step_run_text(data_runtime_switch_evidence_job),
        ]
    )
    assert "write-legacy-to-dual" in data_runtime_switch_runs
    assert "read-legacy-to-new" in data_runtime_switch_runs
    assert "write-dual-to-new" in data_runtime_switch_runs
    assert (
        "uv run python -m scripts.release.verify_post_deploy"
        in data_runtime_switch_runs
    )

    data_schema_inputs = data_schema_workflow["on"]["workflow_dispatch"]["inputs"]
    assert {
        "image_tag",
        "schema_phase",
        "confirm_contract_ready",
        "confirm_schema_apply",
    } <= set(data_schema_inputs)

    data_schema_job = workflow_job(data_schema_workflow, "apply_schema")
    data_schema_evidence_job = workflow_job(data_schema_workflow, "evidence")

    assert data_schema_job["environment"] == "aws"
    assert {
        "Validate image tag",
        "Capture current runtime modes",
        "Guard contract-phase preconditions",
        "Render liquibase task definition",
        "Register liquibase task definition",
        "Run Liquibase",
    } <= set(step_names(data_schema_job))
    assert "Upload data schema apply evidence" in step_names(data_schema_evidence_job)
    data_schema_runs = "\n".join(
        [step_run_text(data_schema_job), step_run_text(data_schema_evidence_job)]
    )
    assert "ci_run_ecs_task.sh" in data_schema_runs
    assert "ci_deploy_ecs_service.sh" not in data_schema_runs
    assert "contract-ready" in data_schema_runs
    assert "READ_MODE=new and WRITE_MODE=new" in data_schema_runs

    data_backfill_inputs = data_backfill_workflow["on"]["workflow_dispatch"]["inputs"]
    assert {"image_tag", "confirm_backfill"} <= set(data_backfill_inputs)

    data_backfill_job = workflow_job(data_backfill_workflow, "run_backfill")
    data_backfill_evidence_job = workflow_job(data_backfill_workflow, "evidence")

    assert data_backfill_job["environment"] == "aws"
    assert {
        "Resolve root domain",
        "Capture current runtime modes",
        "Render backfill task definition",
        "Register backfill task definition",
        "Run backfill worker",
    } <= set(step_names(data_backfill_job))
    assert "Upload data backfill evidence" in step_names(data_backfill_evidence_job)
    data_backfill_runs = "\n".join(
        [step_run_text(data_backfill_job), step_run_text(data_backfill_evidence_job)]
    )
    assert "READ_MODE=legacy" in data_backfill_runs
    assert "WRITE_MODE=dual" in data_backfill_runs
    assert "ci_run_ecs_task.sh" in data_backfill_runs
    assert "ci_deploy_ecs_service.sh" not in data_backfill_runs

    apply_inputs = infra_apply_workflow["on"]["workflow_dispatch"]["inputs"]
    assert {
        "plan_run_id",
        "confirm_apply",
        "allow_ecs_task_definition_changes",
    } <= set(apply_inputs)

    infra_plan_text = read_text(".github/workflows/infra-plan.yml")
    assert "continue-on-error" not in infra_plan_text

    apply_job = workflow_job(infra_apply_workflow, "apply")
    apply_evidence_job = workflow_job(infra_apply_workflow, "evidence")
    plan_job = workflow_job(infra_plan_workflow, "plan")

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
    assert "status=${PIPESTATUS[0]}" in step_run_text(plan_job)


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
    assert "examples/**" not in semgrep_workflow["on"]["pull_request"]["paths"]
    assert "examples/**" not in semgrep_workflow["on"]["push"]["paths"]
    assert "Run Semgrep Community Edition" in step_names(semgrep_job)
    assert "semgrep scan --config auto apps/ packages/ scripts/" in (
        step_run_text(semgrep_job)
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


def test_app_deploy_uses_repo_owned_task_definition_renderer() -> None:
    render_script = read_text("scripts/ci/ci_render_ecs_task_definition.sh")
    python_renderer = read_text("scripts/ci/render_ecs_task_definition.py")

    assert "python3 scripts/ci/render_ecs_task_definition.py" in render_script
    assert "aws ecs describe-task-definition" not in render_script
    assert "describe-task-definition" not in python_renderer
    assert "render_task_definition(" in python_renderer
    assert "_render_primary_edge(" in python_renderer
    assert "_render_event_consumer(" in python_renderer
