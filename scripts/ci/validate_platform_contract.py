#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import ast
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "platform" / "workloads.json"
DEFAULT_RUNTIME_CONTRACT = ROOT / "platform" / "runtime-capabilities.json"
REQUIRED_RUNTIME_LOG_LABELS = {"stack", "environment", "service", "container"}
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
IMAGE_REPOSITORY_RE = re.compile(r"^[a-z0-9][a-z0-9/-]*[a-z0-9]$")
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
CURRENT_RUNTIME_TERRAFORM_ROOTS = {
    "bootstrap": "infra/platform",
    "runtime": "infra/app",
}
DATABASE_URL_ENV_BY_WORKLOAD = {
    "api": "DATABASE_URL",
    "order_event_consumer": "DATABASE_URL",
    "backfill_worker": "BACKFILL_DATABASE_URL",
    "data_export_job": "DATA_EXPORT_DATABASE_URL",
}
COMPOSED_DATABASE_ENV = {"DB_HOST", "DB_PORT", "DB_USER", "DB_NAME"}
PROVIDER_NEUTRAL_RUNTIME_PROVIDES = {
    "ingress",
    "workload_identity",
    "secret_injection",
    "config_injection",
    "logs",
    "metrics",
    "traces",
    "deploy",
    "rollback",
    "one_off_jobs",
    "object_storage",
    "postgres_connectivity",
}
ALLOWED_PROVIDER_EDGE_PREFIXES = (
    ".github/",
    "compose.yaml",
    "dapr/",
    "docs/",
    "infra/",
    "observability/",
    "platform/",
    "scripts/",
    "tests/",
)
PROVIDER_CONFIG_TERMS = {"AWS", "ECS", "RDS", "GITHUB", "CLOUDWATCH"}
CAPABILITY_SPEC_FIELDS = {
    "description",
    "provides",
    "owned_by",
    "evidence_paths",
}

sys.path.insert(0, str(ROOT))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _env_name_to_settings_field(name: str) -> str:
    return name.lower()


def _settings_fields(
    root: Path, workload: dict[str, Any], errors: list[str]
) -> set[str]:
    name = str(workload.get("name", "<unknown>"))
    config_path = root / str(workload.get("app_path", "")) / "config.py"
    if not config_path.is_file():
        errors.append(f"{name}: app_path must contain config.py")
        return set()

    try:
        tree = ast.parse(config_path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"{name}: config.py is not parseable: {exc}")
        return set()

    fields: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "Settings":
            continue
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                if item.target.id != "model_config":
                    fields.add(item.target.id)
    return fields


def _tracked_file_text(root: Path, prefix: str) -> str:
    base = root / prefix
    if base.is_file():
        return base.read_text(encoding="utf-8")
    if not base.exists():
        return ""
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(base.rglob("*"))
        if path.is_file()
        and path.suffix
        in {".md", ".py", ".sh", ".tf", ".tfvars", ".yaml", ".yml", ".json"}
    )


def _runtime_edge_text(root: Path) -> str:
    return "\n".join(
        _tracked_file_text(root, prefix) for prefix in ALLOWED_PROVIDER_EDGE_PREFIXES
    )


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
    image = workload.get("image", {})
    repository = image.get("repository") if isinstance(image, dict) else None
    dockerfile_value = image.get("dockerfile", "") if isinstance(image, dict) else ""
    non_root_user = (
        image.get("non_root_user", "app") if isinstance(image, dict) else "app"
    )
    dockerfile = root / str(dockerfile_value)
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

    if not isinstance(repository, str) or not IMAGE_REPOSITORY_RE.fullmatch(repository):
        errors.append(
            f"{name}: image.repository must be a lowercase image repository name"
        )

    if not dockerfile.is_file():
        errors.append(f"{name}: image.dockerfile does not exist: {dockerfile}")
    else:
        dockerfile_text = dockerfile.read_text(encoding="utf-8")
        for required in [
            "FROM ",
            "RUN uv sync --frozen --no-dev --package",
            f"USER {non_root_user}",
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
    database_url_env = DATABASE_URL_ENV_BY_WORKLOAD.get(name)
    if database_url_env is not None:
        missing_database_env = sorted(
            ({database_url_env} | COMPOSED_DATABASE_ENV) - set(env)
        )
        if missing_database_env:
            errors.append(
                f"{name}: database config.env is missing {missing_database_env}"
            )
        if "DB_PASSWORD" not in secrets:
            errors.append(f"{name}: database config.secrets must include DB_PASSWORD")

    settings_fields = _settings_fields(root, workload, errors)
    for env_name in [*env, *secrets]:
        field_name = _env_name_to_settings_field(env_name)
        if settings_fields and field_name not in settings_fields:
            errors.append(
                f"{name}: config name {env_name} must map to Settings.{field_name}"
            )
        if any(term in env_name for term in PROVIDER_CONFIG_TERMS):
            errors.append(f"{name}: config name {env_name} must stay provider-neutral")

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

    database = workload.get("database")
    if database_url_env is not None:
        if not isinstance(database, dict):
            errors.append(f"{name}: database portability metadata must be declared")
        else:
            if database.get("semantics") != "postgresql":
                errors.append(f"{name}: database.semantics must be postgresql")
            if database.get("runtime_secret") != "DB_PASSWORD":
                errors.append(f"{name}: database.runtime_secret must be DB_PASSWORD")
            pooling = database.get("pooling")
            expected_pooling = "transaction_pool" if name == "api" else "direct"
            if pooling != expected_pooling:
                errors.append(f"{name}: database.pooling must be {expected_pooling}")

    _check_conformance_contract(workload, errors)


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


def _check_conformance_contract(workload: dict[str, Any], errors: list[str]) -> None:
    name = str(workload.get("name", "<unknown>"))
    config = workload.get("config", {})
    env = set(_as_strings(config.get("env")))
    secrets = set(_as_strings(config.get("secrets")))
    conformance = workload.get("conformance")
    if not isinstance(conformance, dict):
        errors.append(f"{name}: conformance metadata must be declared")
        return

    conformance_env = conformance.get("env")
    conformance_secrets = conformance.get("secrets")
    if not isinstance(conformance_env, dict):
        errors.append(f"{name}: conformance.env must map declared env names to values")
        conformance_env = {}
    if not isinstance(conformance_secrets, dict):
        errors.append(
            f"{name}: conformance.secrets must map declared secret names to placeholders"
        )
        conformance_secrets = {}

    if set(conformance_env) != env:
        errors.append(
            f"{name}: conformance.env must match config.env exactly: "
            f"declared={sorted(env)} conformance={sorted(conformance_env)}"
        )
    if set(conformance_secrets) != secrets:
        errors.append(
            f"{name}: conformance.secrets must match config.secrets exactly: "
            f"declared={sorted(secrets)} conformance={sorted(conformance_secrets)}"
        )
    for secret_name, placeholder in conformance_secrets.items():
        if not isinstance(placeholder, str) or not placeholder.startswith(
            "runtime-secret://"
        ):
            errors.append(
                f"{name}: conformance secret {secret_name} must use runtime-secret:// placeholder"
            )

    fields = _as_strings(conformance.get("expected_log_fields"))
    if not fields:
        errors.append(f"{name}: conformance.expected_log_fields must be declared")
    if workload.get("kind") == "service":
        if not isinstance(conformance.get("port"), int):
            errors.append(f"{name}: service conformance.port must be declared")
        if not isinstance(conformance.get("expected_log_event"), str):
            errors.append(f"{name}: service conformance.expected_log_event is required")
    if workload.get("kind") == "job":
        if not isinstance(conformance.get("timeout_seconds"), int):
            errors.append(f"{name}: job conformance.timeout_seconds must be declared")
        expected = conformance.get("expected_success_event")
        if expected != workload.get("job", {}).get("success_event"):
            errors.append(
                f"{name}: conformance.expected_success_event must match job.success_event"
            )


def _check_release_evidence(contract: dict[str, Any], errors: list[str]) -> None:
    import importlib.util

    _spec = importlib.util.spec_from_file_location(
        "release_event",
        ROOT / "scripts" / "observability" / "release_event.py",
    )
    if _spec is None or _spec.loader is None:
        raise ImportError(
            "Cannot locate scripts/observability/release_event.py — "
            "ensure the file exists relative to the repository root."
        )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    REQUIRED_EVENT_FIELDS = _mod.REQUIRED_EVENT_FIELDS

    declared = set(
        _as_strings(contract.get("release_evidence", {}).get("required_fields"))
    )
    implemented = {".".join(path) for path in REQUIRED_EVENT_FIELDS}
    if declared != implemented:
        errors.append(
            "release_evidence.required_fields must match "
            "scripts.observability.release_event.REQUIRED_EVENT_FIELDS"
        )


def _check_runtime_wiring(
    root: Path, workloads: list[dict[str, Any]], errors: list[str]
) -> None:
    edge_text = _runtime_edge_text(root)
    dockerfile_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "apps").glob("*/Dockerfile"))
    )
    env_example = (root / ".env.example").read_text(encoding="utf-8")
    app_config_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "apps").glob("*/config.py"))
    )

    for workload in workloads:
        name = str(workload.get("name", "<unknown>"))
        config = workload.get("config", {})
        for env_name in _as_strings(config.get("env")):
            if env_name not in edge_text and env_name not in str(
                workload.get("conformance", {})
            ):
                errors.append(f"{name}: config env {env_name} is not wired at an edge")
        for secret_name in _as_strings(config.get("secrets")):
            if secret_name not in edge_text:
                errors.append(f"{name}: secret {secret_name} is not wired at an edge")
            for label, text in [
                ("Dockerfiles", dockerfile_text),
                (".env.example", env_example),
            ]:
                if f"{secret_name}=" in text:
                    errors.append(
                        f"{name}: secret {secret_name} must not be set in {label}"
                    )

    for term in PROVIDER_CONFIG_TERMS:
        if term in app_config_text:
            errors.append(f"app config must not name provider concept {term}")


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
    portable_provides = set(_as_strings(contract.get("required_portable_provides")))
    if portable_provides != PROVIDER_NEUTRAL_RUNTIME_PROVIDES:
        errors.append(
            "runtime required_portable_provides must match the provider-neutral capability contract"
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
        if not isinstance(roots, dict):
            errors.append(f"{name}: terraform_roots must be an object")
        else:
            for owner in ["bootstrap", "runtime"]:
                root_path = roots.get(owner)
                if not isinstance(root_path, str):
                    errors.append(f"{name}: terraform_roots.{owner} must be declared")
                    continue
                if not root_path.startswith("infra/"):
                    errors.append(
                        f"{name}: terraform_roots.{owner} must stay under infra/"
                    )
                    continue
                if target.get("status") == "current":
                    expected_path = CURRENT_RUNTIME_TERRAFORM_ROOTS[owner]
                    if root_path != expected_path:
                        errors.append(
                            f"{name}: terraform_roots.{owner} must be {expected_path}"
                        )
                        continue
                if not (root / root_path).is_dir():
                    errors.append(f"{name}: terraform root is missing: {root_path}")
        if target.get("status") != "current" and isinstance(roots, dict):
            root_values = [value for value in roots.values() if isinstance(value, str)]
            if len(set(root_values)) != len(root_values):
                errors.append(f"{name}: terraform roots must have distinct ownership")
            for root_path in root_values:
                for forbidden in ["apps/", "packages/domain", "packages/application"]:
                    root_text = _tracked_file_text(root, root_path)
                    if forbidden in root_text:
                        errors.append(
                            f"{name}: runtime root {root_path} must not import app internals {forbidden}"
                        )

        capabilities = target.get("capabilities")
        if not isinstance(capabilities, dict):
            errors.append(f"{name}: capabilities must be an object")
            continue
        if set(capabilities) != REQUIRED_RUNTIME_CAPABILITIES:
            errors.append(
                f"{name}: capabilities must match required_capabilities exactly"
            )

        provided_contract: dict[str, list[str]] = {}
        for capability in sorted(REQUIRED_RUNTIME_CAPABILITIES):
            spec = capabilities.get(capability)
            if not isinstance(spec, dict):
                errors.append(f"{name}: capability {capability} must be an object")
                continue

            extra_fields = sorted(set(spec) - CAPABILITY_SPEC_FIELDS)
            if extra_fields:
                errors.append(
                    f"{name}: capability {capability} has unsupported fields {extra_fields}"
                )
            owned_by = _as_strings(spec.get("owned_by"))
            evidence_paths = _as_strings(spec.get("evidence_paths"))
            provides = _as_strings(spec.get("provides"))
            if not owned_by:
                errors.append(f"{name}: capability {capability} needs owned_by")
            if not evidence_paths:
                errors.append(f"{name}: capability {capability} needs evidence_paths")
            if not isinstance(spec.get("description"), str) or not spec["description"]:
                errors.append(f"{name}: capability {capability} needs a description")
            for provided in provides:
                if provided not in PROVIDER_NEUTRAL_RUNTIME_PROVIDES:
                    errors.append(
                        f"{name}: capability {capability} provides unknown key {provided}"
                    )
                    continue
                provided_contract.setdefault(provided, []).append(capability)
            for owner_path in [*owned_by, *evidence_paths]:
                if not (root / owner_path).exists():
                    errors.append(
                        f"{name}: capability {capability} owner/evidence path is missing: {owner_path}"
                    )
        if set(provided_contract) != PROVIDER_NEUTRAL_RUNTIME_PROVIDES:
            errors.append(
                f"{name}: portable provides must match required_portable_provides exactly"
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

    _check_runtime_wiring(root, workloads, errors)
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
