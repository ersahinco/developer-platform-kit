from pathlib import Path


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
        "aws_sdlc_api",
        "aws_sdlc_backfill_worker",
        "aws_sdlc_data_export_job",
        "aws_sdlc_order_event_consumer",
        "aws_sdlc_infrastructure",
    ]

    for package in ["domain", "application"]:
        text = _python_text(ROOT / "packages" / package / "src")
        for name in forbidden:
            assert f"import {name}" not in text
            assert f"from {name}" not in text


def test_domain_does_not_import_application_layer() -> None:
    text = _python_text(ROOT / "packages" / "domain" / "src")

    assert "aws_sdlc_application" not in text


def test_api_has_no_direct_event_transport_publish_path() -> None:
    text = _python_text(ROOT / "apps" / "api" / "src")

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
    text = _python_text(ROOT / "apps" / "api" / "src")

    for forbidden in [
        "INSERT INTO customers",
        "SELECT id, name, created_at FROM customers",
    ]:
        assert forbidden not in text


def test_background_hosts_keep_sql_and_storage_in_infrastructure() -> None:
    for app in ["backfill-worker", "data-export-job", "order-event-consumer"]:
        text = _python_text(ROOT / "apps" / app / "src")
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
