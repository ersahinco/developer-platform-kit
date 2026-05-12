#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "platform" / "workloads.json"
REQUIRED_RUNTIME_LOG_LABELS = {"stack", "environment", "service", "container"}

sys.path.insert(0, str(ROOT))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _source_text(root: Path, workload: dict[str, Any]) -> str:
    app_path = root / str(workload["app_path"])
    parts = []
    for path in sorted(app_path.rglob("*.py")):
        parts.append(path.read_text(encoding="utf-8"))
    for path in sorted((root / "packages" / "application").rglob("*.py")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _has_fastapi_get(source: str, path: str) -> bool:
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("@app.get(") and f'"{path}"' in stripped:
            return True
    return False


def _check_common(root: Path, workload: dict[str, Any], errors: list[str]) -> None:
    name = str(workload.get("name", "<unknown>"))
    app_path = root / str(workload.get("app_path", ""))
    package = str(workload.get("package", ""))
    dockerfile = root / str(workload.get("image", {}).get("dockerfile", ""))
    pyproject = app_path / "pyproject.toml"

    if not app_path.is_dir():
        errors.append(f"{name}: app_path does not exist: {app_path}")
        return
    if not (app_path / "main.py").is_file():
        errors.append(f"{name}: app_path must contain main.py")
    if not pyproject.is_file():
        errors.append(f"{name}: app_path must contain pyproject.toml")
    else:
        pyproject_text = pyproject.read_text(encoding="utf-8")
        if f'packages = ["{package}"]' not in pyproject_text:
            errors.append(f"{name}: pyproject must expose package {package!r}")
        if f'package-dir = {{ {package} = "." }}' not in pyproject_text:
            errors.append(f"{name}: pyproject must map package {package!r} to app root")

    if not dockerfile.is_file():
        errors.append(f"{name}: image.dockerfile does not exist: {dockerfile}")
    else:
        dockerfile_text = dockerfile.read_text(encoding="utf-8")
        for required in [
            "FROM ",
            "RUN uv sync --frozen --no-dev --package",
            f"USER {workload.get('image', {}).get('non_root_user', 'app')}",
            'ENV PYTHONPATH="/app/apps:/app/packages"',
            "CMD ",
        ]:
            if required not in dockerfile_text:
                errors.append(f"{name}: Dockerfile missing {required!r}")
        if "PASSWORD=" in dockerfile_text or "SECRET=" in dockerfile_text:
            errors.append(f"{name}: Dockerfile must not bake secret values")

    config = workload.get("config", {})
    if not _as_strings(config.get("env")):
        errors.append(f"{name}: config.env must declare runtime environment keys")
    if not isinstance(config.get("secrets"), list):
        errors.append(f"{name}: config.secrets must be a list, even when empty")

    logs = workload.get("logs", {})
    runtime_labels = set(_as_strings(logs.get("runtime_labels")))
    if runtime_labels != REQUIRED_RUNTIME_LOG_LABELS:
        errors.append(
            f"{name}: logs.runtime_labels must be {sorted(REQUIRED_RUNTIME_LOG_LABELS)}"
        )
    app_fields = _as_strings(logs.get("app_fields"))
    if "event" in app_fields:
        source = _source_text(root, workload)
        for field in app_fields:
            if field not in source:
                errors.append(f"{name}: log field {field!r} is not present in source")

    if not isinstance(workload.get("release_evidence"), list):
        errors.append(f"{name}: release_evidence must declare expected evidence fields")
    if not isinstance(workload.get("rollback"), str):
        errors.append(f"{name}: rollback expectation must be declared")


def _check_service(root: Path, workload: dict[str, Any], errors: list[str]) -> None:
    name = str(workload["name"])
    source = _source_text(root, workload)
    pyproject = (root / str(workload["app_path"]) / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    http = workload.get("http", {})
    for endpoint_name in ["health", "ready", "metrics"]:
        path = http.get(endpoint_name)
        if not isinstance(path, str):
            errors.append(f"{name}: http.{endpoint_name} must be declared")
            continue
        if not _has_fastapi_get(source, path):
            errors.append(f"{name}: missing FastAPI GET endpoint {path}")

    for metric_name in _as_strings(workload.get("metrics", {}).get("required_names")):
        if metric_name not in source:
            errors.append(f"{name}: missing Prometheus metric {metric_name}")
    if "prometheus-client" not in pyproject:
        errors.append(f"{name}: service metrics require prometheus-client dependency")

    if "request_id" in _as_strings(workload.get("logs", {}).get("app_fields")):
        if "X-Request-ID" not in source:
            errors.append(f"{name}: request_id log contract requires X-Request-ID")

    traces = workload.get("traces", {})
    if traces.get("supported") is True:
        for required in ["opentelemetry", "configure_tracing"]:
            if required not in (source + pyproject):
                errors.append(f"{name}: trace support missing {required!r}")


def _check_job(root: Path, workload: dict[str, Any], errors: list[str]) -> None:
    name = str(workload["name"])
    source = _source_text(root, workload)
    if "FastAPI(" in source:
        errors.append(f"{name}: job workloads must not expose service HTTP endpoints")
    job = workload.get("job", {})
    if not isinstance(job.get("idempotency"), str):
        errors.append(f"{name}: job.idempotency must be declared")
    for key in ["success_event"]:
        value = job.get(key)
        if not isinstance(value, str) or value not in source:
            errors.append(f"{name}: job.{key} must name an emitted structured event")


def _check_release_evidence(contract: dict[str, Any], errors: list[str]) -> None:
    from scripts.observability.release_event import REQUIRED_EVENT_FIELDS

    declared = set(
        _as_strings(contract.get("release_evidence", {}).get("required_fields"))
    )
    implemented = {".".join(path) for path in REQUIRED_EVENT_FIELDS}
    if declared != implemented:
        errors.append(
            "release_evidence.required_fields must match "
            "scripts.observability.release_event.REQUIRED_EVENT_FIELDS"
        )


def collect_errors(
    root: Path = ROOT,
    contract_path: Path = DEFAULT_CONTRACT,
) -> list[str]:
    contract = _load_json(contract_path)
    errors: list[str] = []

    if contract.get("schema_version") != "1":
        errors.append("schema_version must be '1'")

    workloads = contract.get("workloads")
    if not isinstance(workloads, list) or not workloads:
        return ["workloads must be a non-empty list"]

    declared_names = {
        str(workload.get("name"))
        for workload in workloads
        if isinstance(workload, dict) and workload.get("name")
    }
    app_names = {
        path.name
        for path in (root / "apps").iterdir()
        if path.is_dir() and (path / "pyproject.toml").is_file()
    }
    if declared_names != app_names:
        errors.append(
            f"workloads must match apps with pyproject.toml: declared={sorted(declared_names)} apps={sorted(app_names)}"
        )

    for workload in workloads:
        if not isinstance(workload, dict):
            errors.append("each workload must be an object")
            continue
        kind = workload.get("kind")
        _check_common(root, workload, errors)
        if kind == "service":
            _check_service(root, workload, errors)
        elif kind == "job":
            _check_job(root, workload, errors)
        else:
            errors.append(
                f"{workload.get('name', '<unknown>')}: kind must be service or job"
            )

    _check_release_evidence(contract, errors)
    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        for error in errors:
            print(f"platform contract: {error}", file=sys.stderr)
        return 1
    print("platform contract: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
