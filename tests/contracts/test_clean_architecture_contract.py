from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def _python_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    )


def test_domain_and_application_do_not_import_outer_layers() -> None:
    forbidden = [
        "fastapi",
        "sqlalchemy",
        "boto3",
        "api",
        "backfill_worker",
        "data_export_job",
        "order_event_consumer",
        "infrastructure",
    ]

    for package in ["domain", "application"]:
        text = _python_text(ROOT / "packages" / package)
        for name in forbidden:
            assert f"import {name}" not in text
            assert f"from {name}" not in text


def test_domain_and_application_stay_cloud_and_delivery_agnostic() -> None:
    text = "\n".join(
        _python_text(ROOT / "packages" / package)
        for package in ["domain", "application"]
    ).lower()

    for forbidden in [
        "terraform",
        "github",
        "cloudwatch",
        "grafana",
        "prometheus",
        "loki",
        "tempo",
        "opentelemetry",
        "s3",
        "sqs",
        "sns",
    ]:
        assert forbidden not in text


def test_domain_does_not_import_application_layer() -> None:
    text = _python_text(ROOT / "packages" / "domain")

    assert "application" not in text


def test_api_has_no_direct_event_transport_publish_path() -> None:
    text = _python_text(ROOT / "apps" / "api")

    for forbidden in [
        "boto3",
        "".join(("Sqs", "Order", "Event", "Publisher")),
        "_".join(("ORDER", "EVENTS", "QUEUE", "URL")),
        "_".join(("dispatch", "outbox", "inline")),
        "DaprOrderEventPublisher",
        "/v1.0/publish",
    ]:
        assert forbidden not in text


def test_api_admin_fixture_does_not_own_customer_sql() -> None:
    text = _python_text(ROOT / "apps" / "api")

    for forbidden in [
        "INSERT INTO customers",
        "SELECT id, name, created_at FROM customers",
    ]:
        assert forbidden not in text


def test_background_hosts_keep_sql_and_storage_in_infrastructure() -> None:
    for app in ["backfill_worker", "data_export_job", "order_event_consumer"]:
        text = _python_text(ROOT / "apps" / app)
        for forbidden in [
            "from sqlalchemy",
            "import sqlalchemy",
            "create_engine",
            "import boto3",
        ]:
            assert forbidden not in text


def test_app_settings_do_not_name_current_runtime_provider() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "apps").glob("*/config.py"))
    )

    for forbidden in ["ECS", "RDS", "Secrets Manager", "CloudWatch"]:
        assert forbidden not in text


def test_object_storage_provider_sdk_stays_in_infrastructure() -> None:
    tracked_files = subprocess.run(
        ["git", "ls-files", "*.py"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    offenders = []
    for tracked_file in tracked_files:
        path = ROOT / tracked_file
        if path == Path(__file__):
            continue
        text = path.read_text(encoding="utf-8")
        if "import boto3" in text or "from boto3" in text:
            offenders.append(tracked_file)

    assert offenders == ["packages/infrastructure/data_export.py"]


def test_docs_do_not_describe_stale_core_adapter_or_direct_sqs_model() -> None:
    paths = [
        ROOT / "README.md",
        *sorted((ROOT / ".github" / "workflows").rglob("*.yml")),
        *sorted((ROOT / "docs").rglob("*.md")),
        *sorted((ROOT / "db").rglob("*.yaml")),
        *sorted((ROOT / "tests").rglob("*.py")),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    forbidden_terms = [
        "/".join(("packages", "core")),
        "/".join(("packages", "adapters")),
        "_".join(("aws", "sdlc", "core")),
        "_".join(("aws", "sdlc", "adapters")),
        " ".join(("SQS", "publish")),
        " ".join(("SQS", "publishing")),
        "-".join(("SQS", "backed")) + " order event",
    ]

    for forbidden in forbidden_terms:
        assert forbidden not in text


def test_canonical_docs_do_not_contain_session_prompt_blocks() -> None:
    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT / "README.md",
            *sorted((ROOT / "docs").rglob("*.md")),
        ]
    )

    forbidden_terms = [
        "\n## Prompt\n",
        "You are working in the aws-sdlc-containers repo.",
        "Start by reading:",
        "Evaluate critically:",
        "Current known remaining gaps to consider:",
    ]

    for forbidden in forbidden_terms:
        assert forbidden not in docs


def test_long_running_workloads_implement_portable_app_contract() -> None:
    for app_name in ["api", "order_event_consumer"]:
        text = (ROOT / "apps" / app_name / "main.py").read_text(encoding="utf-8")

        for required in [
            '@app.get("/health"',
            '@app.get("/ready"',
            '@app.get("/metrics"',
            "CONTENT_TYPE_LATEST",
            "Counter(",
            "Histogram(",
            "X-Request-ID",
        ]:
            assert required in text


def test_app_workloads_have_committed_oci_image_contracts() -> None:
    for app_dir in sorted((ROOT / "apps").iterdir()):
        if not app_dir.is_dir() or not (app_dir / "pyproject.toml").is_file():
            continue

        dockerfile = app_dir / "Dockerfile"
        assert dockerfile.is_file()
        text = dockerfile.read_text(encoding="utf-8")
        package_name = app_dir.name

        for required in [
            "FROM python:3.14-slim",
            f"COPY apps/{package_name}/pyproject.toml",
            f"COPY apps/{package_name}",
            "RUN uv sync --frozen --no-dev --package",
            "USER app",
            'ENV PATH="/app/.venv/bin:$PATH"',
            'ENV PYTHONPATH="/app/apps:/app/packages"',
            "CMD ",
        ]:
            assert required in text


def test_source_tree_is_flat_and_importable_by_folder_name() -> None:
    expected_files = [
        ROOT / "apps" / "api" / "main.py",
        ROOT / "apps" / "backfill_worker" / "main.py",
        ROOT / "apps" / "data_export_job" / "main.py",
        ROOT / "apps" / "order_event_consumer" / "main.py",
        ROOT / "packages" / "domain" / "order.py",
        ROOT / "packages" / "application" / "order_submission.py",
        ROOT / "packages" / "infrastructure" / "db" / "repository.py",
    ]

    for path in expected_files:
        assert path.is_file()

    stale_paths = [
        ROOT / "apps" / "api" / "src",
        ROOT / "apps" / "backfill-worker",
        ROOT / "apps" / "data-export-job",
        ROOT / "apps" / "order-event-consumer",
        ROOT / "packages" / "domain" / "src",
        ROOT / "packages" / "application" / "src",
        ROOT / "packages" / "infrastructure" / "src",
    ]

    for path in stale_paths:
        assert not path.exists()

    tracked_files = subprocess.run(
        ["git", "ls-files", "apps", "packages"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    assert not [path for path in tracked_files if ".egg-info/" in path]


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
    providers_tf = (ROOT / "infra" / "app" / "providers.tf").read_text(encoding="utf-8")
    app_tf = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "infra" / "app").glob("*.tf"))
    )

    assert 'data "terraform_remote_state" "platform"' in providers_tf
    assert "platform = data.terraform_remote_state.platform.outputs" in providers_tf
    assert 'source  = "../platform"' not in app_tf
    assert "data.aws_vpc" not in app_tf
    assert "data.aws_subnets" not in app_tf


def test_portability_status_documents_intentional_provider_boundaries() -> None:
    doc = (ROOT / "docs" / "portability-status.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "roadmaps.md").read_text(encoding="utf-8")
    app_build = (ROOT / ".github" / "workflows" / "app-build.yml").read_text(
        encoding="utf-8"
    )
    platform_contract = (ROOT / "docs" / "platform-contract.md").read_text(
        encoding="utf-8"
    )
    runtime_contract = (ROOT / "docs" / "runtime-capability-contract.md").read_text(
        encoding="utf-8"
    )
    runtime_checklist = (ROOT / "docs" / "runtime-addition-checklist.md").read_text(
        encoding="utf-8"
    )
    workload_contract = (ROOT / "docs" / "workload-onboarding-contract.md").read_text(
        encoding="utf-8"
    )
    database_contract = (ROOT / "docs" / "database-portability-contract.md").read_text(
        encoding="utf-8"
    )
    dapr_contract = (ROOT / "docs" / "dapr-portability-contract.md").read_text(
        encoding="utf-8"
    )
    config_contract = (ROOT / "docs" / "config-secrets-contract.md").read_text(
        encoding="utf-8"
    )
    observability_onboarding = (
        ROOT / "docs" / "observability-onboarding-contract.md"
    ).read_text(encoding="utf-8")
    ci_quality_contract = (ROOT / "docs" / "ci-quality-contract.md").read_text(
        encoding="utf-8"
    )
    data_object_contract = (
        ROOT / "docs" / "data-object-storage-portability.md"
    ).read_text(encoding="utf-8")
    toolkit_checklists = (ROOT / "docs" / "portable-toolkit-checklists.md").read_text(
        encoding="utf-8"
    )

    assert "docs/portability-status.md" in readme
    assert "docs/platform-contract.md" in readme
    assert "docs/runtime-capability-contract.md" in readme
    assert "docs/runtime-addition-checklist.md" in readme
    assert "docs/workload-onboarding-contract.md" in readme
    assert "docs/database-portability-contract.md" in readme
    assert "docs/dapr-portability-contract.md" in readme
    assert "docs/config-secrets-contract.md" in readme
    assert "docs/observability-onboarding-contract.md" in readme
    assert "docs/ci-quality-contract.md" in readme
    assert "docs/data-object-storage-portability.md" in readme
    assert "docs/portable-toolkit-checklists.md" in readme
    assert "Portable Baseline" in doc
    assert "Intentional Provider Dependencies" in doc
    assert "Current Gaps" in doc
    assert "App/platform contract" in doc
    assert "Runtime capability contract" in doc
    assert "packages/domain" in doc
    assert "packages/application" in doc
    assert "Grafana CloudWatch datasource" in doc
    assert "LOKI_PUSH_URL" in doc
    assert "OpenTelemetry Collector" in doc
    assert "Alternate runtime platform" in doc
    assert "Infra rollback stays reviewed `Infra Plan` plus `Infra Apply`" in doc
    assert "portability boundaries" in roadmap
    assert "portable app/platform contract" in roadmap.lower()
    assert "runtime capability contract" in roadmap.lower()
    assert (ROOT / "platform" / "workloads.json").is_file()
    assert (ROOT / "platform" / "runtime-capabilities.json").is_file()
    assert (ROOT / "scripts" / "ci" / "validate_platform_contract.py").is_file()
    assert app_build.count('- "platform/**"') == 2
    assert "uv run python scripts/ci/validate_platform_contract.py" in app_build

    for phrase in [
        "platform/workloads.json",
        "scripts/ci/validate_platform_contract.py",
        "OCI image",
        "/health",
        "/ready",
        "/metrics",
        "structured lines",
        "request_id",
        "OTLP/HTTP traces",
        "environment variables",
        "runtime secret mechanism",
        "One-off and scheduled workloads must also be clear about",
        "Idempotency",
        "Prometheus, Loki, Tempo, and Grafana",
        "release evidence artifacts",
        "Markdown/JSON/JSONL",
        "schema_version",
        "revision.image_tag",
        "github.run_id",
        "correlation.github_run_id",
        "App image rollback",
        "One-off job rollback",
        "Runtime data-phase rollback",
        "Infra rollback uses reviewed `Infra Plan` and `Infra Apply`",
        "does not add a Kubernetes, Nomad, Azure, Google Cloud, or",
    ]:
        assert phrase in platform_contract

    runtime_contract_lower = runtime_contract.lower()
    for phrase in [
        "platform/runtime-capabilities.json",
        "container runtime",
        "networking",
        "identity",
        "secrets",
        "ingress",
        "observability",
        "jobs",
        "rollout",
        "rollback",
        "release evidence",
        "cost controls",
        "terraform ownership",
        "local/ci guardrails",
        "eks",
        "azure",
        "gcp",
        "without changing app/domain code",
        "platform/delivery edges",
        "docs/runtime-addition-checklist.md",
    ]:
        assert phrase in runtime_contract_lower

    runtime_checklist_lower = runtime_checklist.lower()
    for phrase in [
        "future runtime addition checklist",
        "platform/runtime-capabilities.json",
        "platform/workloads.json",
        "packages/domain",
        "packages/application",
        "prometheus metrics",
        "loki-compatible logs",
        "otlp/http traces",
        "provider-native observability is allowed",
        "provider-managed infrastructure",
        "cloudwatch",
        "terraform roots under `infra/`",
        "app image rollback",
        "runtime data rollback",
        "infra rollback",
        "same markdown/json/jsonl schema",
        "uv run python scripts/ci/validate_platform_contract.py",
    ]:
        assert phrase in runtime_checklist_lower

    workload_contract_lower = workload_contract.lower()
    for phrase in [
        "workload onboarding contract",
        "apps/<name>/main.py",
        "apps/<name>/dockerfile",
        "/health",
        "/ready",
        "/metrics",
        "platform/workloads.json",
        "rollback",
        "release evidence",
        "provider-specific env names",
    ]:
        assert phrase in workload_contract_lower

    database_contract_lower = database_contract.lower()
    for phrase in [
        "database portability contract",
        "postgresql semantics",
        "rds is the current aws runtime implementation",
        "supabase",
        "liquibase",
        "pgbouncer",
        "db_password",
        "database_url",
        "backup",
        "restore",
        "cloudwatch is acceptable for rds",
        "cloudwatch must not become",
        "packages/infrastructure/db",
    ]:
        assert phrase in database_contract_lower

    dapr_contract_lower = dapr_contract.lower()
    for phrase in [
        "dapr portability contract",
        "dapr pub/sub",
        "cloudevents",
        "sns/sqs",
        "redis",
        "kafka",
        "azure service bus",
        "gcp pub/sub",
        "outbox",
        "idempotency",
        "provider-native sqs metrics",
    ]:
        assert phrase in dapr_contract_lower

    config_contract_lower = config_contract.lower()
    for phrase in [
        "config and secrets contract",
        "upper snake case",
        "platform/workloads.json",
        "a name cannot be both config and secret",
        "db_password",
        "runtime secret mechanism",
        "github actions env",
        "future runtime",
    ]:
        assert phrase in config_contract_lower

    observability_onboarding_lower = observability_onboarding.lower()
    for phrase in [
        "observability onboarding contract",
        "prometheus",
        "loki-compatible structured logs",
        "otlp/http traces",
        "grafana",
        "no cloudwatch datasource is required",
        "incident",
        "query hints",
    ]:
        assert phrase in observability_onboarding_lower

    ci_quality_contract_lower = ci_quality_contract.lower()
    for phrase in [
        "ci quality contract",
        "github actions",
        "ruff format check",
        "pyright",
        "pytest",
        "validate_platform_contract.py",
        "actionlint",
        "gitleaks",
        "checkov",
        "trivy",
        "reviewed plan",
    ]:
        assert phrase in ci_quality_contract_lower

    data_object_contract_lower = data_object_contract.lower()
    for phrase in [
        "data and object storage portability",
        "s3 is the current aws implementation",
        "raw/",
        "curated/",
        "manifests/",
        "sha-256 checksum",
        "data_export_s3_bucket",
        "gcs",
        "azure blob",
        "supabase storage",
        "provider sdk imports stay out",
    ]:
        assert phrase in data_object_contract_lower

    toolkit_checklists_lower = toolkit_checklists.lower()
    for phrase in [
        "workload-onboarding-contract.md",
        "dapr-portability-contract.md",
        "config-secrets-contract.md",
        "observability-onboarding-contract.md",
        "ci-quality-contract.md",
        "data-object-storage-portability.md",
        "new workload",
        "dapr eventing",
        "config and secrets",
        "observability onboarding",
        "ci quality gates",
        "data and object storage",
        "platform/workloads.json",
        "prometheus metrics",
        "loki-compatible structured logs",
        "otlp/http traces",
        "github actions",
        "terraform fmt -check -recursive infra",
        "s3 is the current aws object-storage implementation",
        "supabase storage",
    ]:
        assert phrase in toolkit_checklists_lower
