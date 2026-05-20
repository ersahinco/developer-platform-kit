from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ._helpers import ROOT, load_json, read_text


ENV_NAME_PATTERN = re.compile(
    r'env_(?:str|int|bool|float|optional_int)\("([A-Z0-9_]+)"'
)


def _runtime_conformance() -> dict[str, Any]:
    return load_json("platform/runtime-conformance.json")


def _workload_conformance(
    workload: dict[str, Any], conformance: dict[str, Any]
) -> dict[str, Any]:
    defaults = conformance.get("defaults", {})
    default_env = dict(defaults.get("env", {}))  # type: ignore[union-attr]
    default_secrets = dict(defaults.get("secrets", {}))  # type: ignore[union-attr]
    workload_fixture = dict(conformance["workloads"][workload["name"]])  # type: ignore[index]
    database = workload["database"]
    default_env["DB_HOST"] = (
        "pgbouncer" if database["pooling"] == "transaction_pool" else "db"
    )
    workload_fixture["env"] = {**default_env, **dict(workload_fixture.get("env", {}))}
    workload_fixture["secrets"] = {
        **default_secrets,
        **dict(workload_fixture.get("secrets", {})),
    }
    return workload_fixture


def _compose_service_name(workload: dict[str, Any]) -> str:
    return str(workload["image"]["repository"])


def _config_path(workload: dict[str, Any]) -> Path:
    return ROOT / str(workload["app_path"]) / "config.py"


def _declared_config_names(workload: dict[str, Any]) -> set[str]:
    return set(workload["config"]["env"]) | set(workload["config"]["secrets"])


def test_workload_registry_has_required_shape() -> None:
    contract = load_json("platform/workloads.json")
    conformance = _runtime_conformance()

    for workload in contract["workloads"]:
        assert workload["name"] in conformance["workloads"]

        workload_conformance = _workload_conformance(workload, conformance)
        if workload["kind"] == "service":
            assert "startup_timeout_seconds" in workload_conformance
        else:
            assert "timeout_seconds" in workload_conformance


def test_workload_contract_stays_portable() -> None:
    workloads_json = read_text("platform/workloads.json").lower()
    forbidden_runtime_markers = [
        "arn:",
        ".amazonaws.com",
        "aws_",
        '"ecs',
        '"ecr',
        '"rds',
        '"cloudwatch',
        '"eventbridge',
        '"wafv2',
        "s3://",
    ]

    for marker in forbidden_runtime_markers:
        assert marker not in workloads_json


def test_workload_registry_maps_to_real_app_files() -> None:
    contract = load_json("platform/workloads.json")

    for workload in contract["workloads"]:
        app_path = ROOT / workload["app_path"]
        assert app_path.is_dir()
        assert (app_path / "main.py").is_file()
        assert (app_path / "config.py").is_file()
        assert (app_path / "pyproject.toml").is_file()


def test_compose_build_args_and_ports_align_with_workload_spec() -> None:
    contract = load_json("platform/workloads.json")
    compose = yaml.safe_load(read_text("compose.yaml"))
    services = compose["services"]

    for workload in contract["workloads"]:
        compose_name = _compose_service_name(workload)
        compose_service = services[compose_name]
        build_args = compose_service["build"]["args"]

        assert build_args["APP_PATH"] == workload["app_path"]
        assert build_args["UV_PACKAGE"] == workload["image"]["package"]
        assert build_args["WORKLOAD_CMD"] == workload["image"]["command"]

        if workload["kind"] == "service":
            port = workload["service"]["port"]
            declared_ports = compose_service.get("ports", [])
            if declared_ports:
                assert any(str(port) in declared for declared in declared_ports)

    order_consumer = next(
        workload
        for workload in contract["workloads"]
        if workload["name"] == "order_event_consumer"
    )
    dapr = order_consumer["dapr"]
    dapr_service = services["order-event-consumer-dapr"]
    workload_service = services["order-event-consumer"]
    command = dapr_service["command"]
    env = workload_service["environment"]

    assert command[command.index("--app-id") + 1] == dapr["app_id"]
    assert command[command.index("--app-port") + 1] == str(
        order_consumer["service"]["port"]
    )
    assert env["ORDER_EVENTS_APP_PORT"] == str(order_consumer["service"]["port"])
    assert env["ORDER_EVENTS_PUBSUB_NAME"] == dapr["pubsub_name"]
    assert env["ORDER_EVENTS_TOPIC"] == dapr["topic"]


def test_workload_spec_config_names_match_app_settings() -> None:
    contract = load_json("platform/workloads.json")
    shared_config_text = read_text("packages/infrastructure/config.py")
    shared_names = set(ENV_NAME_PATTERN.findall(shared_config_text))

    for workload in contract["workloads"]:
        config_text = _config_path(workload).read_text(encoding="utf-8")
        discovered_names = set(ENV_NAME_PATTERN.findall(config_text))
        if "PostgresRuntimeSettings" in config_text:
            discovered_names |= shared_names
        assert _declared_config_names(workload) == discovered_names


def test_compose_workload_env_names_stay_within_declared_contract() -> None:
    contract = load_json("platform/workloads.json")
    compose = yaml.safe_load(read_text("compose.yaml"))
    services = compose["services"]

    for workload in contract["workloads"]:
        compose_name = _compose_service_name(workload)
        compose_env = set(services[compose_name].get("environment", {}).keys())
        assert compose_env.issubset(_declared_config_names(workload))


def test_compose_database_wiring_matches_declared_pooling_model() -> None:
    contract = load_json("platform/workloads.json")
    compose = yaml.safe_load(read_text("compose.yaml"))
    services = compose["services"]

    for workload in contract["workloads"]:
        compose_name = _compose_service_name(workload)
        env = services[compose_name].get("environment", {})
        expected_host = (
            "pgbouncer"
            if workload["database"]["pooling"] == "transaction_pool"
            else "db"
        )

        assert env["DB_HOST"] == expected_host
        for key, value in env.items():
            if key.endswith("DATABASE_URL"):
                assert f"@{expected_host}:5432/" in value


def test_runtime_conformance_uses_declared_workload_config_names() -> None:
    contract = load_json("platform/workloads.json")
    conformance = _runtime_conformance()

    for workload in contract["workloads"]:
        workload_conformance = _workload_conformance(workload, conformance)
        conformance_names = set(workload_conformance["env"]) | set(
            workload_conformance["secrets"]
        )
        assert conformance_names.issubset(_declared_config_names(workload))
