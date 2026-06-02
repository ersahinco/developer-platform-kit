from __future__ import annotations

import json
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast
from urllib import error, request

import pytest

ROOT = Path(__file__).resolve().parents[2]
POSTGRES_IMAGE = "postgres:18.3"
PGBOUNCER_IMAGE = "edoburu/pgbouncer:v1.25.1-p0"
SERVICE_HTTP_PATHS = {
    "health": "/health",
    "ready": "/ready",
    "metrics": "/metrics",
}
RUNTIME_LABELS = ("stack", "environment", "service", "container")
TRANSIENT_DOCKER_BUILD_ERRORS = (
    "504 Gateway Time-out",
    "502 Bad Gateway",
    "503 Service Unavailable",
    "TLS handshake timeout",
    "i/o timeout",
    "EOF",
    "connection reset by peer",
)


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _run_docker_build(
    args: list[str], retries: int = 2
) -> subprocess.CompletedProcess[str]:
    attempts = retries + 1
    for attempt in range(1, attempts + 1):
        try:
            return _run(args)
        except subprocess.CalledProcessError as exc:
            if (
                args[:2] != ["docker", "build"]
                or attempt == attempts
                or not any(
                    marker in exc.stderr for marker in TRANSIENT_DOCKER_BUILD_ERRORS
                )
            ):
                raise
            time.sleep(attempt)
    raise AssertionError("unreachable")


def _docker_available() -> bool:
    try:
        _run(["docker", "ps"])
    except FileNotFoundError, subprocess.CalledProcessError:
        return False
    return True


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _load_workloads() -> list[dict[str, object]]:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    conformance = json.loads(
        (ROOT / "platform" / "runtime-conformance.json").read_text()
    )
    default_env = dict(conformance.get("defaults", {}).get("env", {}))
    default_secrets = dict(conformance.get("defaults", {}).get("secrets", {}))
    workloads = [
        workload
        for workload in contract["workloads"]
        if "local-compose" in workload["runtime"]["supported"]
    ]
    merged: list[dict[str, object]] = []
    for workload in workloads:
        item = dict(workload)
        workload_conformance = dict(conformance["workloads"][workload["name"]])
        database = workload.get("database")
        workload_env = dict(default_env) if isinstance(database, dict) else {}
        if isinstance(database, dict):
            workload_env["DB_HOST"] = (
                "pgbouncer" if database["pooling"] == "transaction_pool" else "db"
            )
        workload_env.update(dict(workload_conformance.get("env", {})))
        workload_secrets = dict(default_secrets) if isinstance(database, dict) else {}
        workload_secrets.update(dict(workload_conformance.get("secrets", {})))
        workload_conformance["env"] = workload_env
        workload_conformance["secrets"] = workload_secrets
        item["conformance"] = workload_conformance
        merged.append(item)
    return merged


def _json_logs(container: str) -> list[dict[str, object]]:
    logs = _run(["docker", "logs", container]).stdout.splitlines()
    parsed = []
    for line in logs:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            parsed.append(value)
    return parsed


def _http_json(
    url: str,
    timeout: float = 2.0,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _http_text(url: str, timeout: float = 2.0) -> tuple[int, str, str]:
    req = request.Request(url)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return (
                response.status,
                response.headers.get("content-type", ""),
                response.read().decode("utf-8"),
            )
    except error.HTTPError as exc:
        return exc.code, exc.headers.get("content-type", ""), exc.read().decode("utf-8")


def _wait_for_http(url: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status, _ = _http_json(url)
            if status == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(1)
    raise AssertionError(f"{url} did not become healthy: {last_error}")


def _wait_for_container_health(
    container: str, timeout_seconds: int = 60, host: str | None = None
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        command = ["docker", "exec", container, "pg_isready", "-U", "postgres"]
        if host is not None:
            command.extend(["-h", host, "-p", "5432"])
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    raise AssertionError(f"{container} did not become database-ready")


@contextmanager
def _runtime_dependencies() -> Iterator[tuple[str, str]]:
    prefix = f"runtime-conformance-{uuid.uuid4().hex[:10]}"
    network = f"{prefix}-net"
    db = f"{prefix}-db"
    pgbouncer = f"{prefix}-pgbouncer"
    created_containers: list[str] = []
    try:
        _run(["docker", "network", "create", network])
        _run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                db,
                "--network",
                network,
                "--network-alias",
                "db",
                "-e",
                "POSTGRES_DB=aws_sdlc_containers",
                "-e",
                "POSTGRES_USER=postgres",
                "-e",
                "POSTGRES_PASSWORD=postgres",
                POSTGRES_IMAGE,
            ]
        )
        created_containers.append(db)
        _wait_for_container_health(db)

        _run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                pgbouncer,
                "--network",
                network,
                "--network-alias",
                "pgbouncer",
                "-e",
                "DB_HOST=db",
                "-e",
                "DB_PORT=5432",
                "-e",
                "DB_NAME=aws_sdlc_containers",
                "-e",
                "DB_USER=postgres",
                "-e",
                "DB_PASSWORD=postgres",
                "-e",
                "POOL_MODE=transaction",
                "-e",
                "DEFAULT_POOL_SIZE=20",
                "-e",
                "MAX_CLIENT_CONN=200",
                "-e",
                "AUTH_TYPE=scram-sha-256",
                PGBOUNCER_IMAGE,
            ]
        )
        created_containers.append(pgbouncer)
        _wait_for_container_health(pgbouncer, host="localhost")

        liquibase_image = f"{prefix}-liquibase"
        _run(["docker", "build", "-t", liquibase_image, "db"])
        _run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                network,
                "-v",
                f"{ROOT / 'db'}:/liquibase/db",
                liquibase_image,
                "--changelog-file=changelog/db.changelog-master.yaml",
                "--search-path=/liquibase/db",
                "--url=jdbc:postgresql://db:5432/aws_sdlc_containers",
                "--username=postgres",
                "--password=postgres",
                "update",
            ]
        )
        yield network, prefix
    finally:
        for container in created_containers:
            subprocess.run(["docker", "rm", "-f", container], cwd=ROOT, check=False)
        subprocess.run(["docker", "network", "rm", network], cwd=ROOT, check=False)


@pytest.fixture(scope="session")
def runtime_network() -> Iterator[tuple[str, str]]:
    if not _docker_available():
        pytest.fail("Docker is required for runtime conformance")
    with _runtime_dependencies() as value:
        yield value


def _build_image(workload: dict[str, object], prefix: str) -> str:
    name = str(workload["name"])
    image_spec = cast(dict[str, Any], workload["image"])
    build_args = {
        "APP_PATH": str(workload["app_path"]),
        "UV_PACKAGE": str(image_spec["package"]),
        "WORKLOAD_CMD": str(image_spec["command"]),
    }
    dockerfile = str(image_spec.get("dockerfile", "platform/workload.Dockerfile"))
    context = str(image_spec.get("context", "."))
    image = f"{prefix}-{name}:local"
    args = ["docker", "build", "-f", dockerfile, "-t", image]
    for key, value in build_args.items():
        args.extend(["--build-arg", f"{key}={value}"])
    args.append(context)
    _run_docker_build(args)
    return image


def _env_args(conformance: dict[str, object]) -> list[str]:
    args: list[str] = []
    env = dict(conformance["env"])  # type: ignore[arg-type]
    secrets = dict(conformance["secrets"])  # type: ignore[arg-type]
    for name, value in {**env, **{key: "postgres" for key in secrets}}.items():
        args.extend(["-e", f"{name}={value}"])
    return args


def _run_service_probes(
    *,
    base_url: str,
    container: str,
    conformance: dict[str, object],
) -> None:
    probes = conformance.get("service_probes", [])
    if not isinstance(probes, list):
        return

    for probe in probes:
        if not isinstance(probe, dict):
            continue
        method = str(probe.get("method", "GET"))
        path = str(probe["path"])
        payload = probe.get("json")
        if payload is not None and not isinstance(payload, dict):
            raise AssertionError(f"service probe for {path} has non-object json")
        status, response_payload = _http_json(
            f"{base_url}{path}",
            method=method,
            payload=cast(dict[str, object] | None, payload),
        )
        assert status == int(probe.get("expected_status", 200))
        response_fields = set(probe.get("expected_response_fields", []))
        assert response_fields.issubset(response_payload.keys())

        expected_log_event = probe.get("expected_log_event")
        if not isinstance(expected_log_event, str):
            continue
        expected_log_fields = set(probe.get("expected_log_fields", []))
        logs = _json_logs(container)
        assert any(
            entry.get("event") == expected_log_event
            and expected_log_fields.issubset(entry.keys())
            for entry in logs
        )


def test_declared_service_images_satisfy_portable_runtime_contract(
    runtime_network: tuple[str, str],
) -> None:
    network, prefix = runtime_network
    for workload in [item for item in _load_workloads() if item["kind"] == "service"]:
        name = str(workload["name"])
        conformance = workload["conformance"]  # type: ignore[index]
        assert isinstance(conformance, dict)
        service = cast(dict[str, object], workload["service"])
        port = int(cast(int | str, service["port"]))
        host_port = _free_port()
        image = _build_image(workload, prefix)
        container = f"{prefix}-{name}"
        try:
            _run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    container,
                    "--network",
                    network,
                    "--label",
                    "stack=runtime-conformance",
                    "--label",
                    "environment=local",
                    "--label",
                    f"service={name}",
                    "--label",
                    f"container={name}",
                    "-p",
                    f"127.0.0.1:{host_port}:{port}",
                    *_env_args(conformance),
                    image,
                ]
            )
            base_url = f"http://127.0.0.1:{host_port}"
            try:
                _wait_for_http(
                    f"{base_url}{SERVICE_HTTP_PATHS['health']}",
                    int(conformance["startup_timeout_seconds"]),
                )
            except AssertionError as exc:
                logs = subprocess.run(
                    ["docker", "logs", container],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                raise AssertionError(
                    f"{name} did not become healthy.\nSTDOUT:\n{logs.stdout}\nSTDERR:\n{logs.stderr}"
                ) from exc

            health_status, health_payload = _http_json(
                f"{base_url}{SERVICE_HTTP_PATHS['health']}"
            )
            assert health_status == 200
            assert health_payload["status"] == "ok"

            ready_status, ready_payload = _http_json(
                f"{base_url}{SERVICE_HTTP_PATHS['ready']}"
            )
            assert ready_status == 200
            assert ready_payload["status"] == "ready"
            checks = ready_payload["checks"]
            assert isinstance(checks, dict)
            if "database" in workload:
                assert checks["database"] == "ok"
            else:
                assert checks

            metrics_status, content_type, metrics = _http_text(
                f"{base_url}{SERVICE_HTTP_PATHS['metrics']}"
            )
            assert metrics_status == 200
            assert "text/plain" in content_type
            for metric_name in workload["metrics"]["required_names"]:  # type: ignore[index]
                assert metric_name in metrics

            labels = json.loads(
                _run(
                    [
                        "docker",
                        "inspect",
                        container,
                        "--format",
                        "{{json .Config.Labels}}",
                    ]
                ).stdout
            )
            for key in RUNTIME_LABELS:
                assert key in labels

            logs = _json_logs(container)
            expected_event = conformance["expected_log_event"]
            expected_fields = set(conformance["expected_log_fields"])  # type: ignore[arg-type]
            assert any(
                entry.get("event") == expected_event
                and expected_fields.issubset(entry.keys())
                for entry in logs
            )
            _run_service_probes(
                base_url=base_url,
                container=container,
                conformance=conformance,
            )
        finally:
            subprocess.run(["docker", "rm", "-f", container], cwd=ROOT, check=False)


def test_declared_job_images_satisfy_portable_runtime_contract(
    runtime_network: tuple[str, str],
) -> None:
    network, prefix = runtime_network
    for workload in [item for item in _load_workloads() if item["kind"] == "job"]:
        name = str(workload["name"])
        conformance = workload["conformance"]  # type: ignore[index]
        assert isinstance(conformance, dict)
        image = _build_image(workload, prefix)
        container = f"{prefix}-{name}"
        try:
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--name",
                    container,
                    "--network",
                    network,
                    "--label",
                    "stack=runtime-conformance",
                    "--label",
                    "environment=local",
                    "--label",
                    f"service={name}",
                    "--label",
                    f"container={name}",
                    *_env_args(conformance),
                    image,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=int(conformance["timeout_seconds"]),
            )
            assert result.returncode == 0, result.stderr + result.stdout
            logs = _json_logs(container)
            expected_event = conformance["expected_success_event"]
            expected_fields = set(conformance["expected_log_fields"])  # type: ignore[arg-type]
            assert any(
                entry.get("event") == expected_event
                and expected_fields.issubset(entry.keys())
                for entry in logs
            )
        finally:
            subprocess.run(["docker", "rm", "-f", container], cwd=ROOT, check=False)
