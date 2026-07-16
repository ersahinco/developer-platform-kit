from __future__ import annotations

import re
import tomllib
from typing import Any

import yaml

from ._helpers import load_json, read_text, runtime_admitted, runtime_supported


ENV_NAME_PATTERN = re.compile(
    r'env_(?:str|int|bool|float|optional_int)\("([A-Z0-9_]+)"'
)
USE_CASE_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
IDEMPOTENCY_PATTERN = re.compile(r"[a-z0-9]+(?:[_-][a-z0-9]+)*")


def _runtime_conformance() -> dict[str, Any]:
    return load_json("platform/runtime-conformance.json")


def _declared_owner(workload: dict[str, Any]) -> str:
    return str(workload["owner"])


def _runtime_supported(workload: dict[str, Any]) -> set[str]:
    return runtime_supported(str(workload["name"]))


def _runtime_admitted(workload: dict[str, Any]) -> set[str]:
    return runtime_admitted(str(workload["name"]))


def _supports_local_runtime(workload: dict[str, Any]) -> bool:
    return "local-compose" in _runtime_supported(workload)


def _declared_database(workload: dict[str, Any]) -> dict[str, Any] | None:
    database = workload.get("database")
    return database if isinstance(database, dict) else None


def _workload_conformance(
    workload: dict[str, Any], conformance: dict[str, Any]
) -> dict[str, Any]:
    defaults = conformance.get("defaults", {})
    default_env: dict[str, Any] = {}
    default_secrets: dict[str, Any] = {}
    workload_fixture = dict(conformance["workloads"][workload["name"]])  # type: ignore[index]
    database = _declared_database(workload)
    if database is not None:
        default_env = dict(defaults.get("env", {}))  # type: ignore[union-attr]
        default_secrets = dict(defaults.get("secrets", {}))  # type: ignore[union-attr]
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


def _declared_config_names(workload: dict[str, Any]) -> set[str]:
    return set(workload["config"]["env"]) | set(workload["config"]["secrets"])


WORKLOAD_CHOREOGRAPHY_KEYS = {
    "aws",
    "ecs",
    "terraform",
    "workflow",
    "cluster",
    "subnet",
    "security_group",
    "task_definition",
    "service_name",
    "desired_count",
    "cpu",
    "memory",
    "iam",
    "role_arn",
    "policy_arn",
    "bucket",
    "queue",
    "topic_arn",
    "load_balancer",
    "target_group",
    "schedule_expression",
    "cron",
}


def _walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            nested_key
            for nested_value in value.values()
            for nested_key in _walk_keys(nested_value)
        }
    if isinstance(value, list):
        return {
            nested_key
            for nested_value in value
            for nested_key in _walk_keys(nested_value)
        }
    return set()


def test_workload_registry_has_required_shape() -> None:
    contract = load_json("platform/workloads.json")
    conformance = _runtime_conformance()
    workload_names = {
        workload["name"]
        for workload in contract["workloads"]
        if _supports_local_runtime(workload)
    }

    assert set(conformance["workloads"]) == workload_names

    for workload in contract["workloads"]:
        assert "patterns" not in workload
        workload_conformance = _workload_conformance(workload, conformance)
        if workload["kind"] == "service":
            assert "startup_timeout_seconds" in workload_conformance
        else:
            assert "timeout_seconds" in workload_conformance


def test_workload_contract_does_not_encode_deployment_choreography() -> None:
    contract = load_json("platform/workloads.json")

    for workload in contract["workloads"]:
        forbidden_keys = _walk_keys(workload) & WORKLOAD_CHOREOGRAPHY_KEYS
        assert forbidden_keys == set()


def test_compose_build_args_and_ports_align_with_workload_spec() -> None:
    contract = load_json("platform/workloads.json")
    compose = yaml.safe_load(read_text("compose.yaml"))
    services = compose["services"]

    for workload in contract["workloads"]:
        if not _supports_local_runtime(workload):
            continue
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

    for workload in contract["workloads"]:
        dapr = workload.get("dapr")
        if dapr is None or not _supports_local_runtime(workload):
            continue
        compose_name = _compose_service_name(workload)
        dapr_service = services[f"{compose_name}-dapr"]
        command = dapr_service["command"]
        assert command[command.index("--app-id") + 1] == dapr["app_id"]
        assert command[command.index("--app-port") + 1] == str(
            workload["service"]["port"]
        )

        if dapr["scope"] == "pubsub":
            env = services[compose_name]["environment"]
            assert env["DAPR_PUBSUB_NAME"] == dapr["pubsub_name"]
            assert env["DAPR_TOPIC"] == dapr["topic"]
            assert env["DAPR_SUBSCRIPTION_ROUTE"] == dapr["subscription_route"]


def test_shared_workload_dockerfile_copies_workspace_pyproject_files() -> None:
    workspace = tomllib.loads(read_text("pyproject.toml"))["tool"]["uv"]["workspace"]
    dockerfile = read_text("platform/workload.Dockerfile")

    for member in workspace["members"]:
        assert f"COPY {member}/pyproject.toml {member}/pyproject.toml" in dockerfile


def test_workload_spec_config_names_match_app_settings() -> None:
    contract = load_json("platform/workloads.json")
    shared_config_text = read_text("packages/infrastructure/config.py")
    shared_names = set(ENV_NAME_PATTERN.findall(shared_config_text))

    for workload in contract["workloads"]:
        config_text = read_text(f"{workload['app_path']}/config.py")
        discovered_names = set(ENV_NAME_PATTERN.findall(config_text))
        if "PostgresRuntimeSettings" in config_text:
            discovered_names |= shared_names
        assert _declared_config_names(workload) == discovered_names


def test_object_output_is_declared_without_a_provider_binding() -> None:
    workloads = {
        workload["name"]: workload
        for workload in load_json("platform/workloads.json")["workloads"]
    }

    assert workloads["data_export_job"]["object_output"] == {
        "format": "csv-with-json-manifest",
        "integrity": "sha256",
    }
    assert all(
        "object_output" not in workload
        for name, workload in workloads.items()
        if name != "data_export_job"
    )


def test_workload_runtime_support_and_admission_are_explicit() -> None:
    contract = load_json("platform/workloads.json")
    support = load_json("platform/workload-runtime-support.json")
    workload_names = {workload["name"] for workload in contract["workloads"]}

    assert support["schema_version"] == "1"
    for target, profile in support["targets"].items():
        supported_names = set(profile["supported_workloads"])
        admitted_names = set(profile["admitted_workloads"])
        assert supported_names <= workload_names, target
        assert admitted_names <= supported_names, target

    for workload in contract["workloads"]:
        supported = _runtime_supported(workload)
        admitted = _runtime_admitted(workload)

        assert supported
        assert admitted.issubset(supported)


def test_aws_runtime_realization_is_sourced_from_workload_contract() -> None:
    workload_inventory = read_text("infra/app/workload_inventory.tf")

    assert 'jsondecode(file("${path.module}/../../platform/workloads.json"))' in (
        workload_inventory
    )
    assert 'local.workload_runtime_support.targets["aws-ecs"].admitted_workloads' in (
        workload_inventory
    )
    assert "workloads_by_name" in workload_inventory
    assert "workload_environment" in workload_inventory
    assert "workload_secrets" in workload_inventory
    assert "unmapped_workload_env" in workload_inventory
    assert "unmapped_workload_secrets" in workload_inventory
    assert "aws_admitted_service_port_gaps" in workload_inventory
    assert 'check "aws_admitted_workload_env_is_realized"' in workload_inventory
    assert 'check "aws_admitted_workload_secrets_are_mapped"' in workload_inventory
    assert 'check "aws_admitted_services_have_runtime_ports"' in workload_inventory


def test_workloads_declare_portable_owner() -> None:
    contract = load_json("platform/workloads.json")

    for workload in contract["workloads"]:
        owner = _declared_owner(workload)
        assert owner
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", owner)


def test_workload_contract_declares_proof_fields_without_runtime_choreography() -> None:
    contract = load_json("platform/workloads.json")

    for workload in contract["workloads"]:
        use_cases = workload.get("use_cases")
        assert isinstance(use_cases, list), workload["name"]
        assert use_cases, workload["name"]
        assert all(USE_CASE_PATTERN.fullmatch(str(use_case)) for use_case in use_cases)

        if workload["kind"] == "service":
            metrics = workload.get("metrics")
            assert isinstance(metrics, dict), workload["name"]
            assert metrics["format"] == "prometheus"
            required_names = metrics.get("required_names")
            assert isinstance(required_names, list), workload["name"]
            assert "workload_info" in required_names
            assert all(isinstance(name, str) and name for name in required_names)

        if workload["kind"] == "job":
            job = workload.get("job")
            assert isinstance(job, dict), workload["name"]
            idempotency = job.get("idempotency")
            assert isinstance(idempotency, str), workload["name"]
            assert IDEMPOTENCY_PATTERN.fullmatch(idempotency), workload["name"]

        dapr = workload.get("dapr")
        if dapr is not None:
            assert dapr["scope"] in {"pubsub", "service-invocation"}
            expected_fields = {"app_id", "scope"}
            if dapr["scope"] == "pubsub":
                expected_fields |= {"pubsub_name", "topic", "subscription_route"}
            assert set(dapr) == expected_fields
            for field in expected_fields:
                assert isinstance(dapr[field], str) and dapr[field], workload["name"]


def test_compose_workload_env_names_stay_within_declared_contract() -> None:
    contract = load_json("platform/workloads.json")
    compose = yaml.safe_load(read_text("compose.yaml"))
    services = compose["services"]

    for workload in contract["workloads"]:
        if not _supports_local_runtime(workload):
            continue
        compose_name = _compose_service_name(workload)
        compose_env = set(services[compose_name].get("environment", {}).keys())
        assert compose_env.issubset(_declared_config_names(workload))


def test_compose_database_wiring_matches_declared_pooling_model() -> None:
    contract = load_json("platform/workloads.json")
    compose = yaml.safe_load(read_text("compose.yaml"))
    services = compose["services"]

    for workload in contract["workloads"]:
        if not _supports_local_runtime(workload):
            continue
        compose_name = _compose_service_name(workload)
        env = services[compose_name].get("environment", {})
        database = _declared_database(workload)
        if database is None:
            assert "DB_HOST" not in env
            assert "DB_PORT" not in env
            continue
        expected_host = (
            "pgbouncer" if database["pooling"] == "transaction_pool" else "db"
        )

        assert env["DB_HOST"] == expected_host
        for key, value in env.items():
            if key.endswith("DATABASE_URL"):
                assert f"@{expected_host}:5432/" in value


def test_workload_conformance_defaults_can_skip_database_for_non_database_workloads() -> (
    None
):
    workload = {
        "name": "analytics_dashboard",
        "kind": "service",
        "config": {"env": ["OTEL_TRACES_ENABLED"], "secrets": []},
    }
    conformance = {
        "defaults": {
            "env": {"DB_PORT": "5432", "DB_USER": "postgres", "DB_NAME": "test"},
            "secrets": {"DB_PASSWORD": "runtime-secret://postgres-password"},
        },
        "workloads": {
            "analytics_dashboard": {
                "startup_timeout_seconds": 30,
                "env": {"OTEL_TRACES_ENABLED": "false"},
                "expected_log_event": "http_request",
                "expected_log_fields": ["event"],
            }
        },
    }

    workload_conformance = _workload_conformance(workload, conformance)

    assert workload_conformance["env"] == {"OTEL_TRACES_ENABLED": "false"}
    assert workload_conformance["secrets"] == {}


def test_runtime_conformance_uses_declared_workload_config_names() -> None:
    contract = load_json("platform/workloads.json")
    conformance = _runtime_conformance()

    for workload in contract["workloads"]:
        if not _supports_local_runtime(workload):
            continue
        workload_conformance = _workload_conformance(workload, conformance)
        conformance_names = set(workload_conformance["env"]) | set(
            workload_conformance["secrets"]
        )
        assert conformance_names.issubset(_declared_config_names(workload))


def test_runtime_conformance_service_probes_remain_fixture_evidence() -> None:
    conformance = _runtime_conformance()
    allowed_keys = {
        "method",
        "path",
        "json",
        "expected_status",
        "expected_response_fields",
        "expected_log_event",
        "expected_log_fields",
    }

    for name, fixture in conformance["workloads"].items():
        probes = fixture.get("service_probes", [])
        assert isinstance(probes, list)
        for probe in probes:
            assert set(probe).issubset(allowed_keys), name
            assert isinstance(probe["path"], str)
            assert probe.get("method", "GET") in {"GET", "POST", "PUT", "PATCH"}
            assert isinstance(probe.get("expected_status", 200), int)
            assert isinstance(probe.get("expected_response_fields", []), list)
            assert isinstance(probe.get("expected_log_fields", []), list)


def test_cloud_data_workflows_use_declared_runtime_mode_endpoints() -> None:
    workflow_paths = [
        ".github/workflows/data-backfill.yml",
        ".github/workflows/data-runtime-switch.yml",
        ".github/workflows/data-schema-apply.yml",
    ]

    for path in workflow_paths:
        text = read_text(path)
        assert "/admin/read-mode" not in text
        assert "/admin/write-mode" not in text
        assert "runtime_mode_endpoints.read" in text
        assert "runtime_mode_endpoints.write" in text


def test_cloud_dry_runs_still_validate_image_availability() -> None:
    workflow_paths = [
        ".github/workflows/app-deploy.yml",
        ".github/workflows/data-backfill.yml",
        ".github/workflows/data-schema-apply.yml",
        ".github/workflows/data-support-deploy.yml",
        ".github/workflows/operational-snapshot.yml",
    ]

    for path in workflow_paths:
        text = read_text(path)
        for match in re.finditer(r"aws ecr describe-images", text):
            preceding_lines = text[: match.start()].splitlines()[-3:]
            assert "if: ${{ !inputs.dry_run }}" not in "\n".join(preceding_lines)


def test_aws_admitted_workload_secrets_have_runtime_mapping_guard() -> None:
    contract = load_json("platform/workloads.json")
    workload_inventory = read_text("infra/app/workload_inventory.tf")
    shared_secret_block = re.search(
        r"shared_secret_value_from = \{(?P<body>.*?)^\s+\}",
        workload_inventory,
        re.MULTILINE | re.DOTALL,
    )
    assert shared_secret_block is not None
    mapped_secret_names = set(
        re.findall(r"^\s+([A-Z0-9_]+)\s*=", shared_secret_block.group("body"), re.M)
    )
    aws_secret_names = {
        secret
        for workload in contract["workloads"]
        if "aws-ecs" in _runtime_admitted(workload)
        for secret in workload["config"]["secrets"]
    }

    assert aws_secret_names.issubset(mapped_secret_names)
    assert "unmapped_workload_secrets" in workload_inventory
    assert 'check "aws_admitted_workload_secrets_are_mapped"' in workload_inventory


def test_aws_admitted_workload_env_has_runtime_realization_guard() -> None:
    contract = load_json("platform/workloads.json")
    workload_inventory = read_text("infra/app/workload_inventory.tf")
    mapped_env_names = set(
        re.findall(r"^\s+([A-Z0-9_]+)\s*=", workload_inventory, re.M)
    ) | set(re.findall(r'"([A-Z0-9_]+)"', workload_inventory))
    aws_env_names = {
        env_name
        for workload in contract["workloads"]
        if "aws-ecs" in _runtime_admitted(workload)
        for env_name in workload["config"]["env"]
    }

    assert aws_env_names.issubset(mapped_env_names)
    assert "unmapped_workload_env" in workload_inventory
    assert "workload_realized_env_names" in workload_inventory
    assert 'check "aws_admitted_workload_env_is_realized"' in workload_inventory


def test_aws_admitted_services_have_runtime_port_guard() -> None:
    contract = load_json("platform/workloads.json")
    workload_inventory = read_text("infra/app/workload_inventory.tf")

    for workload in contract["workloads"]:
        if "aws-ecs" not in _runtime_admitted(workload):
            continue
        if workload["kind"] != "service":
            continue

        port = workload.get("service", {}).get("port")
        assert isinstance(port, int)
        assert 1 <= port <= 65535

    assert "aws_admitted_service_port_gaps" in workload_inventory
    assert "tonumber(workload.service.port)" in workload_inventory
    assert 'check "aws_admitted_services_have_runtime_ports"' in workload_inventory


def test_primary_edge_task_definition_revisions_are_deploy_owned() -> None:
    compute_ecs = read_text("infra/app/compute_ecs.tf")

    task_definition_block = re.search(
        r'resource "aws_ecs_task_definition" "primary_edge" \{(?P<body>.*?)^}',
        compute_ecs,
        re.MULTILINE | re.DOTALL,
    )
    assert task_definition_block is not None
    assert "ignore_changes = [container_definitions]" in task_definition_block.group(
        "body"
    )

    service_block = re.search(
        r'resource "aws_ecs_service" "primary_edge" \{(?P<body>.*?)^}',
        compute_ecs,
        re.MULTILINE | re.DOTALL,
    )
    assert service_block is not None
    assert "task_definition" in service_block.group("body")
    assert "ignore_changes" in service_block.group("body")
