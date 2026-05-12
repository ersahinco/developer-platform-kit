#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "platform" / "workloads.json"
DEFAULT_RUNTIME_CONTRACT = ROOT / "platform" / "runtime-capabilities.json"
REQUIRED_RUNTIME_LOG_LABELS = {"stack", "environment", "service", "container"}
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
REQUIRED_RUNTIME_CAPABILITIES = {
    "container_runtime",
    "networking",
    "identity",
    "secrets",
    "ingress",
    "observability",
    "jobs",
    "rollout",
    "rollback",
    "release_evidence",
    "cost_controls",
    "terraform_ownership",
    "local_ci_guardrails",
}

sys.path.insert(0, str(ROOT))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _check_env_names(
    *,
    workload_name: str,
    label: str,
    names: list[str],
    errors: list[str],
) -> None:
    for name in names:
        if not ENV_NAME_RE.fullmatch(name):
            errors.append(
                f"{workload_name}: {label} entry {name!r} must be UPPER_SNAKE_CASE"
            )


def _source_text(root: Path, workload: dict[str, Any]) -> str:
    app_path = root / str(workload["app_path"])
    parts = []
    for path in sorted(app_path.rglob("*.py")):
        parts.append(path.read_text(encoding="utf-8"))
    for path in sorted((root / "packages" / "application").rglob("*.py")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _joined_file_text(
    root: Path, paths: list[str], errors: list[str], label: str
) -> str:
    parts = []
    for raw_path in paths:
        path = root / raw_path
        if not path.is_file():
            errors.append(f"{label}: proof file does not exist: {raw_path}")
            continue
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
    env = _as_strings(config.get("env"))
    secrets = _as_strings(config.get("secrets"))
    if not env:
        errors.append(f"{name}: config.env must declare runtime environment keys")
    if not isinstance(config.get("secrets"), list):
        errors.append(f"{name}: config.secrets must be a list, even when empty")
    _check_env_names(workload_name=name, label="config.env", names=env, errors=errors)
    _check_env_names(
        workload_name=name,
        label="config.secrets",
        names=secrets,
        errors=errors,
    )
    overlapping_secret_env = sorted(set(env) & set(secrets))
    if overlapping_secret_env:
        errors.append(
            f"{name}: secret names must not also appear in config.env: {overlapping_secret_env}"
        )

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

    traces = workload.get("traces")
    if not isinstance(traces, dict) or not isinstance(traces.get("supported"), bool):
        errors.append(f"{name}: traces.supported must be declared for every workload")
    elif traces["supported"] is True and traces.get("protocol") != "otlp_http":
        errors.append(f"{name}: supported traces must use protocol='otlp_http'")
    elif traces["supported"] is False and traces.get("protocol") is not None:
        errors.append(f"{name}: unsupported traces must use protocol=null")


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


def _check_runtime_contract(
    *,
    root: Path,
    runtime_contract_path: Path,
    errors: list[str],
) -> None:
    contract = _load_json(runtime_contract_path)
    if contract.get("schema_version") != "1":
        errors.append("runtime schema_version must be '1'")

    required = set(_as_strings(contract.get("required_capabilities")))
    if required != REQUIRED_RUNTIME_CAPABILITIES:
        errors.append(
            "runtime required_capabilities must match the portable runtime contract"
        )

    future_rules = _as_strings(contract.get("future_runtime_rules"))
    if len(future_rules) < 3:
        errors.append("runtime future_runtime_rules must document append-only rules")

    targets = contract.get("runtime_targets")
    if not isinstance(targets, list) or not targets:
        errors.append("runtime_targets must be a non-empty list")
        return

    current_targets = [
        target
        for target in targets
        if isinstance(target, dict) and target.get("status") == "current"
    ]
    if len(current_targets) != 1:
        errors.append("exactly one current runtime target must be declared")

    for target in targets:
        if not isinstance(target, dict):
            errors.append("each runtime target must be an object")
            continue

        name = str(target.get("name", "<unknown>"))
        if target.get("workload_contract") != "platform/workloads.json":
            errors.append(
                f"{name}: workload_contract must reference platform/workloads.json"
            )

        if target.get("orchestrator") != "github_actions":
            errors.append(
                f"{name}: orchestrator must be declared as github_actions today"
            )

        roots = target.get("terraform_roots", {})
        for owner, expected_path in {
            "bootstrap": "infra/platform",
            "runtime": "infra/app",
        }.items():
            if not isinstance(roots, dict) or roots.get(owner) != expected_path:
                errors.append(
                    f"{name}: terraform_roots.{owner} must be {expected_path}"
                )
            elif not (root / expected_path).is_dir():
                errors.append(f"{name}: terraform root is missing: {expected_path}")

        capabilities = target.get("capabilities")
        if not isinstance(capabilities, dict):
            errors.append(f"{name}: capabilities must be an object")
            continue
        if set(capabilities) != REQUIRED_RUNTIME_CAPABILITIES:
            errors.append(
                f"{name}: capabilities must match required_capabilities exactly"
            )

        for capability in sorted(REQUIRED_RUNTIME_CAPABILITIES):
            spec = capabilities.get(capability)
            if not isinstance(spec, dict):
                errors.append(f"{name}: capability {capability} must be an object")
                continue

            proof_files = _as_strings(spec.get("proof_files"))
            required_tokens = _as_strings(spec.get("required_tokens"))
            if not proof_files:
                errors.append(f"{name}: capability {capability} needs proof_files")
            if not required_tokens:
                errors.append(f"{name}: capability {capability} needs required_tokens")
            if not isinstance(spec.get("description"), str) or not spec["description"]:
                errors.append(f"{name}: capability {capability} needs a description")

            proof_text = _joined_file_text(
                root,
                proof_files,
                errors,
                f"{name}.{capability}",
            )
            for token in required_tokens:
                if token not in proof_text:
                    errors.append(
                        f"{name}: capability {capability} proof is missing token {token!r}"
                    )


def collect_errors(
    root: Path = ROOT,
    contract_path: Path = DEFAULT_CONTRACT,
    runtime_contract_path: Path = DEFAULT_RUNTIME_CONTRACT,
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
    _check_runtime_contract(
        root=root,
        runtime_contract_path=runtime_contract_path,
        errors=errors,
    )
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
