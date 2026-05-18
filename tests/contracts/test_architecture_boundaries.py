from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _python_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    )


def test_domain_and_application_do_not_import_outer_layers() -> None:
    forbidden = ["fastapi", "sqlalchemy", "boto3", "api", "infrastructure"]

    for package in ["domain", "application"]:
        text = _python_text(ROOT / "packages" / package)
        for name in forbidden:
            assert f"import {name}" not in text
            assert f"from {name}" not in text


def test_domain_does_not_import_application_layer() -> None:
    text = _python_text(ROOT / "packages" / "domain")

    assert "application" not in text


def test_api_has_no_direct_event_transport_publish_path() -> None:
    text = _python_text(ROOT / "apps" / "api")

    for forbidden in ["boto3", "DaprOrderEventPublisher", "/v1.0/publish"]:
        assert forbidden not in text


def test_background_hosts_keep_sql_and_storage_in_infrastructure() -> None:
    for app in ["backfill_worker", "data_export_job", "order_event_consumer"]:
        text = _python_text(ROOT / "apps" / app)
        for forbidden in [
            "from sqlalchemy",
            "import sqlalchemy",
            "import boto3",
        ]:
            assert forbidden not in text


def test_database_portability_is_postgres_not_current_provider() -> None:
    import json

    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    pooling_by_workload = {
        workload["name"]: workload["database"]["pooling"]
        for workload in contract["workloads"]
    }

    assert pooling_by_workload["api"] == "transaction_pool"
    assert pooling_by_workload["backfill_worker"] == "direct"
    assert pooling_by_workload["data_export_job"] == "direct"
    assert pooling_by_workload["order_event_consumer"] == "direct"


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
        if not path.exists():
            continue
        if path == Path(__file__):
            continue
        text = path.read_text(encoding="utf-8")
        if "import boto3" in text or "from boto3" in text:
            offenders.append(tracked_file)

    assert offenders == ["packages/infrastructure/data_export.py"]


def test_dapr_pubsub_boundary_keeps_provider_brokers_at_runtime_edge() -> None:
    import json

    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    order_consumer = next(
        workload
        for workload in contract["workloads"]
        if workload["name"] == "order_event_consumer"
    )
    assert order_consumer["dapr"]["scope"] == "pubsub"
    assert order_consumer["dapr"]["pubsub_name"] == "order-events-pubsub"

    app_facing_text = "\n".join(
        [
            _python_text(ROOT / "packages" / "application"),
            _python_text(ROOT / "apps" / "order_event_consumer"),
            _python_text(ROOT / "packages" / "infrastructure" / "dapr"),
        ]
    ).lower()
    for forbidden in ["sns", "sqs", "localstack", "queue_url", "topic_arn"]:
        assert forbidden not in app_facing_text

    dapr_adapter = _python_text(ROOT / "packages" / "infrastructure" / "dapr")
    runtime_edge = "\n".join(
        [
            _read("infra/app/messaging.tf"),
            _read("platform/dapr/local/components/order-events-pubsub.yaml"),
        ]
    ).lower()
    assert "/v1.0/publish/" in dapr_adapter
    assert "snssqs" in runtime_edge


def test_alternate_dapr_component_can_satisfy_same_pubsub_contract() -> None:
    import yaml

    current = yaml.safe_load(
        (
            ROOT
            / "platform"
            / "dapr"
            / "local"
            / "components"
            / "order-events-pubsub.yaml"
        ).read_text()
    )
    alternate = yaml.safe_load(
        (
            ROOT / "tests" / "fixtures" / "dapr" / "alternate-order-events-pubsub.yaml"
        ).read_text()
    )

    assert current["metadata"]["name"] == "order-events-pubsub"
    assert alternate["metadata"]["name"] == current["metadata"]["name"]
    assert alternate["spec"]["type"].startswith("pubsub.")
