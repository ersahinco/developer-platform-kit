import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _python_files(root: Path) -> list[Path]:
    return [
        path for path in sorted(root.rglob("*.py")) if "__pycache__" not in path.parts
    ]


def _imports(root: Path) -> tuple[set[str], set[str]]:
    top_level: set[str] = set()
    module_paths: set[str] = set()
    for path in _python_files(root):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_paths.add(alias.name)
                    top_level.add(alias.name.split(".", 1)[0])
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                module_paths.add(node.module)
                top_level.add(node.module.split(".", 1)[0])
    return top_level, module_paths


def _string_literals(root: Path) -> set[str]:
    values: set[str] = set()
    for path in _python_files(root):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                values.add(node.value)
    return values


def test_domain_and_application_do_not_import_outer_layers() -> None:
    forbidden = {"fastapi", "sqlalchemy", "boto3", "api", "infrastructure"}

    for package in ["domain", "application"]:
        top_level_imports, _ = _imports(ROOT / "packages" / package)
        assert top_level_imports.isdisjoint(forbidden)


def test_domain_does_not_import_application_layer() -> None:
    top_level_imports, _ = _imports(ROOT / "packages" / "domain")
    assert "application" not in top_level_imports


def test_api_has_no_direct_event_transport_publish_path() -> None:
    top_level_imports, module_paths = _imports(ROOT / "apps" / "api")
    literals = _string_literals(ROOT / "apps" / "api")

    assert "boto3" not in top_level_imports
    assert "infrastructure.dapr.pubsub" not in module_paths
    assert "/v1.0/publish" not in literals


def test_background_hosts_keep_sql_and_storage_in_infrastructure() -> None:
    for app in ["backfill_worker", "data_export_job", "event_consumer"]:
        top_level_imports, _ = _imports(ROOT / "apps" / app)
        assert "sqlalchemy" not in top_level_imports
        assert "boto3" not in top_level_imports


def test_dapr_pubsub_boundary_keeps_provider_brokers_at_runtime_edge() -> None:
    import json

    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    event_consumer = next(
        workload
        for workload in contract["workloads"]
        if workload["name"] == "event_consumer"
    )
    assert event_consumer["dapr"]["app_id"] == "event-consumer"
    assert event_consumer["dapr"]["scope"] == "pubsub"
    assert event_consumer["dapr"]["pubsub_name"] == "async-events-pubsub"

    dapr_adapter = "\n".join(
        path.read_text(encoding="utf-8")
        for path in _python_files(ROOT / "packages" / "infrastructure" / "dapr")
    )
    local_profile = _read(
        "platform/concerns/dapr/profiles/local/components/async-events-pubsub.yaml"
    ).lower()
    production_profile = _read(
        "platform/concerns/dapr/profiles/production/components/async-events-pubsub.yaml"
    ).lower()
    assert "/v1.0/publish/" in dapr_adapter
    assert "pubsub.redis" in local_profile
    assert "snssqs" in production_profile


def test_alternate_dapr_component_can_satisfy_same_pubsub_contract() -> None:
    import yaml

    current = yaml.safe_load(
        (
            ROOT
            / "platform"
            / "concerns"
            / "dapr"
            / "profiles"
            / "local"
            / "components"
            / "async-events-pubsub.yaml"
        ).read_text()
    )
    alternate = yaml.safe_load(
        (
            ROOT / "tests" / "fixtures" / "dapr" / "alternate-async-events-pubsub.yaml"
        ).read_text()
    )

    assert current["metadata"]["name"] == "async-events-pubsub"
    assert alternate["metadata"]["name"] == current["metadata"]["name"]
    assert alternate["spec"]["type"].startswith("pubsub.")
