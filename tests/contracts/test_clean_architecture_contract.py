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

    assert "docs/portability-status.md" in readme
    assert "Portable Baseline" in doc
    assert "Intentional Provider Dependencies" in doc
    assert "Current Gaps" in doc
    assert "packages/domain" in doc
    assert "packages/application" in doc
    assert "Grafana CloudWatch datasource" in doc
    assert "LOKI_PUSH_URL" in doc
    assert "OpenTelemetry Collector" in doc
    assert "Alternate runtime platform" in doc
    assert "Infra rollback stays reviewed `Infra Plan` plus `Infra Apply`" in doc
    assert "portability boundaries" in roadmap
