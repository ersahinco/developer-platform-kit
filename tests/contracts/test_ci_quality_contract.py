from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ci_quality_contract_documents_standard_gate_shape() -> None:
    contract = _read("docs/ci-quality-contract.md")

    for phrase in [
        "GitHub Actions is the current delivery control plane",
        "Ruff format check",
        "Ruff lint",
        "Pyright",
        "pytest",
        "validate_platform_contract.py",
        "actionlint",
        "lychee",
        "hadolint",
        "Gitleaks",
        "pip-audit",
        "Semgrep Community Edition",
        "Trivy",
        "terraform fmt",
        "terraform validate",
        "TFLint",
        "Checkov",
        "reviewed plan",
        "separate apply",
        "tests/contracts/test_ci_quality_contract.py",
    ]:
        assert phrase in contract


def test_makefile_exposes_local_ci_quality_gates() -> None:
    makefile = _read("Makefile")

    for phrase in [
        "lint: secret-scan dependency-audit lint-app lint-scripts lint-docs lint-workflows lint-dockerfiles lint-infra",
        "uv run ruff check apps/ packages/ tests/ scripts/",
        "uv run pyright",
        "find scripts -name '*.sh' -print0 | xargs -0 bash -n",
        "lychee README.md 'docs/**/*.md'",
        "actionlint",
        "hadolint db/Dockerfile db/pgbouncer/Dockerfile observability/firelens/Dockerfile apps/*/Dockerfile",
        "gitleaks dir . --redact --no-banner",
        "uv run pip-audit",
        "terraform fmt -check -recursive infra/",
        "tflint --init",
        "checkov -d infra --framework terraform --config-file infra/.checkov.yaml",
    ]:
        assert phrase in makefile


def test_app_build_workflow_keeps_app_validation_image_and_scan_gates() -> None:
    workflow = _read(".github/workflows/app-build.yml")

    for phrase in [
        "uv sync --frozen --all-packages --group dev --group test",
        "uv run ruff format --check apps/ packages/ tests/ scripts/",
        "uv run ruff check apps/ packages/ tests/ scripts/",
        "uv run pyright",
        "uv run python scripts/ci/validate_platform_contract.py",
        "find scripts -name '*.sh' -print0 | xargs -0 bash -n",
        "Run Liquibase migrations",
        "uv run pytest tests/ -v",
        "docker build -f apps/api/Dockerfile",
        "docker build -f apps/backfill_worker/Dockerfile",
        "docker build -f apps/data_export_job/Dockerfile",
        "docker build -f apps/order_event_consumer/Dockerfile",
        "ghcr.io/aquasecurity/trivy",
        "docker push",
        "actions/attest-build-provenance",
    ]:
        assert phrase in workflow


def test_security_and_sast_workflows_keep_repository_hygiene_gates() -> None:
    security = _read(".github/workflows/security.yml")
    semgrep = _read(".github/workflows/semgrep.yml")

    for phrase in [
        "gitleaks",
        "lycheeverse/lychee-action",
        "rhysd/actionlint",
        "hadolint/hadolint",
        "uv run pip-audit",
    ]:
        assert phrase in security

    assert "semgrep/semgrep" in semgrep
    assert "semgrep scan --config auto apps/ packages/ scripts/" in semgrep


def test_infra_workflows_keep_reviewed_plan_apply_gates() -> None:
    plan = _read(".github/workflows/infra-plan.yml")
    apply = _read(".github/workflows/infra-apply.yml")

    for phrase in [
        "terraform fmt -check -recursive infra",
        "terraform validate",
        "tflint --init",
        "tflint --format compact",
        "bridgecrewio/checkov-action",
        "terraform plan -var-file",
        "actions/upload-artifact",
        "Post plan to PR",
    ]:
        assert phrase in plan

    for phrase in [
        "Expected an Infra Plan workflow run",
        "run.head_branch !== defaultBranch",
        "run.head_sha !== branch.commit.sha",
        "actions/download-artifact",
        "Guard reviewed plan blast radius",
        "ci_guard_infra_plan_blast_radius.sh",
        "terraform apply -auto-approve platform.tfplan",
        "terraform apply -auto-approve app.tfplan",
        "release_event.py",
        "actions/upload-artifact",
    ]:
        assert phrase in apply
