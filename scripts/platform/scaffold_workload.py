from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
import re
import sys
import textwrap
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
USE_CASE_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SCAFFOLD_RUNTIME_TARGETS = ("local-compose", "aws-ecs")
SUPPORTED_WORKLOAD_PATTERNS: dict[str, dict[str, str]] = {
    "edge-service": {
        "kind": "service",
        "operational_class": "edge-service",
    },
    "internal-async-service": {
        "kind": "service",
        "operational_class": "internal-service",
    },
    "operator-job": {
        "kind": "job",
        "operational_class": "operator-job",
    },
    "scheduled-job": {
        "kind": "job",
        "operational_class": "scheduled-job",
    },
    "export-job": {
        "kind": "job",
        "operational_class": "scheduled-job",
    },
}


@dataclass
class RenderedFile:
    path: str
    mode: str
    content: str


@dataclass
class WorkloadScaffoldPlan:
    workload_name: str
    patterns: list[str]
    use_cases: list[str]
    kind: str
    operational_class: str
    files: list[RenderedFile] = field(default_factory=list)
    workload_entry: dict[str, Any] = field(default_factory=dict)
    runtime_conformance_entry: dict[str, Any] = field(default_factory=dict)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _snake_to_kebab(value: str) -> str:
    return value.replace("_", "-")


def _snake_to_upper(value: str) -> str:
    return value.upper()


def _field_name(env_name: str) -> str:
    return env_name.lower()


def _description(name: str, patterns: list[str]) -> str:
    if "edge-service" in patterns:
        return f"Public edge-service workload host for {name}."
    if "internal-async-service" in patterns:
        return f"Internal async workload host for {name}."
    if "export-job" in patterns:
        return f"Scheduled export workload host for {name}."
    if "operator-job" in patterns:
        return f"Operator job workload host for {name}."
    return f"Workload host for {name}."


def _pattern_index() -> dict[str, dict[str, Any]]:
    return SUPPORTED_WORKLOAD_PATTERNS


def _normalized_patterns(values: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(values))
    if "export-job" in normalized and "scheduled-job" not in normalized:
        normalized.insert(0, "scheduled-job")
    return normalized


def _validate_use_cases(values: list[str]) -> None:
    if not values:
        raise ValueError("at least one --use-case is required")
    for value in values:
        if USE_CASE_PATTERN.fullmatch(value) is None:
            raise ValueError(f"invalid use case {value!r}")


def _validate_name(value: str) -> None:
    if NAME_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "workload name must use snake_case with lowercase letters and digits"
        )


def _resolve_kind_and_class(patterns: list[str]) -> tuple[str, str]:
    entries = _pattern_index()
    missing = [pattern for pattern in patterns if pattern not in entries]
    if missing:
        raise ValueError(f"unknown workload pattern(s): {', '.join(sorted(missing))}")

    kinds = {str(entries[pattern]["kind"]) for pattern in patterns}
    classes = {str(entries[pattern]["operational_class"]) for pattern in patterns}
    if len(kinds) != 1:
        raise ValueError(f"patterns disagree on workload kind: {sorted(kinds)}")
    if len(classes) != 1:
        raise ValueError(f"patterns disagree on operational class: {sorted(classes)}")
    return next(iter(kinds)), next(iter(classes))


def _default_database_pooling(patterns: list[str], kind: str) -> str | None:
    if kind == "service":
        if "edge-service" in patterns:
            return "transaction_pool"
        return "direct"
    return "direct"


def _default_traces_supported(patterns: list[str]) -> bool:
    return "edge-service" in patterns


def _resolved_runtime_targets(
    supported: list[str], admitted: list[str]
) -> tuple[list[str], list[str]]:
    supported_targets = list(dict.fromkeys(["local-compose", *supported, *admitted]))
    admitted_targets = list(dict.fromkeys(admitted))
    return supported_targets, admitted_targets


def _database_url_placeholder(name: str, pooling: str | None) -> str | None:
    if pooling is None:
        return None
    host = "pgbouncer" if pooling == "transaction_pool" else "db"
    var_name = f"{_snake_to_upper(name)}_DATABASE_URL"
    return f"${{{var_name}:-postgresql://postgres:postgres@{host}:5432/aws_sdlc_containers}}"


def _database_url_fixture(pooling: str | None) -> str | None:
    if pooling is None:
        return None
    host = "pgbouncer" if pooling == "transaction_pool" else "db"
    return f"postgresql://postgres:postgres@{host}:5432/aws_sdlc_containers"


def _service_env_names(
    patterns: list[str], traces_supported: bool, extra_env: list[str]
) -> list[str]:
    names = ["DATABASE_URL", "DB_HOST", "DB_PORT", "DB_USER", "DB_NAME"]
    if "edge-service" in patterns:
        if traces_supported:
            names.extend(
                [
                    "OTEL_TRACES_ENABLED",
                    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
                    "OTEL_SERVICE_NAME",
                    "OTEL_DEPLOYMENT_ENVIRONMENT",
                ]
            )
        names.extend(
            [
                "RUNTIME_READ_MODE",
                "RUNTIME_WRITE_MODE",
                "ROLLOUT_DRILL_FAULT_MODE",
                "ROLLOUT_DRILL_FAULT_PATHS",
                "ROLLOUT_DRILL_FAULT_STATUS_CODE",
                "ROLLOUT_DRILL_FAULT_DELAY_SECONDS",
            ]
        )
    if "internal-async-service" in patterns:
        names.extend(
            [
                "DAPR_HTTP_ENDPOINT",
                "DAPR_HTTP_PORT",
                "DAPR_PUBSUB_NAME",
                "DAPR_TOPIC",
                "DAPR_SUBSCRIPTION_ROUTE",
            ]
        )
    names.extend(extra_env)
    return names


def _job_env_names(
    database_pooling: str | None,
    patterns: list[str],
    extra_env: list[str],
) -> list[str]:
    names: list[str] = []
    if database_pooling is not None:
        names.extend(["DATABASE_URL", "DB_HOST", "DB_PORT", "DB_USER", "DB_NAME"])
    if "export-job" in patterns:
        names.append("DATA_EXPORT_OUTPUT_DIR")
    names.extend(extra_env)
    return names


def _env_field_block(names: list[str]) -> str:
    field_blocks: list[str] = []
    for env_name in names:
        field_name = _field_name(env_name)
        field_blocks.append(
            textwrap.dedent(
                f"""\
                {field_name}: str | None = field(
                    default_factory=lambda: env_str("{env_name}")
                )
                """
            ).rstrip()
        )
    return "\n\n".join(field_blocks)


def _extra_required_properties(names: list[str]) -> str:
    blocks: list[str] = []
    for env_name in names:
        field_name = _field_name(env_name)
        blocks.append(
            textwrap.dedent(
                f"""\
                    @property
                    def required_{field_name}(self) -> str:
                        return require_value(self.{field_name}, "{env_name}")
                """
            ).rstrip()
        )
    return "\n\n".join(blocks)


def _render_service_config(
    module_name: str,
    patterns: list[str],
    traces_supported: bool,
    extra_env: list[str],
) -> str:
    del module_name
    lines = [
        "from dataclasses import dataclass",
        "from dataclasses import field",
        "",
        "from infrastructure.config import env_bool",
        "from infrastructure.config import env_float",
        "from infrastructure.config import env_int",
        "from infrastructure.config import env_str",
        "from infrastructure.config import load_env_file",
        "from infrastructure.config import PostgresRuntimeSettings",
        "from infrastructure.config import require_value",
        "",
        "",
        "load_env_file()",
        "",
        "",
        "@dataclass",
        "class Settings(PostgresRuntimeSettings):",
        '    database_url: str | None = field(default_factory=lambda: env_str("DATABASE_URL"))',
        '    db_host: str | None = field(default_factory=lambda: env_str("DB_HOST", "localhost"))',
    ]
    if traces_supported:
        lines.extend(
            [
                '    otel_traces_enabled: bool = field(default_factory=lambda: env_bool("OTEL_TRACES_ENABLED"))',
                '    otel_exporter_otlp_traces_endpoint: str | None = field(default_factory=lambda: env_str("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"))',
                '    otel_service_name: str = field(default_factory=lambda: require_value(env_str("OTEL_SERVICE_NAME"), "OTEL_SERVICE_NAME"))',
                '    otel_deployment_environment: str = field(default_factory=lambda: require_value(env_str("OTEL_DEPLOYMENT_ENVIRONMENT", "local"), "OTEL_DEPLOYMENT_ENVIRONMENT"))',
            ]
        )
    if "edge-service" in patterns:
        lines.extend(
            [
                '    runtime_read_mode: str = field(default_factory=lambda: require_value(env_str("RUNTIME_READ_MODE", "legacy"), "RUNTIME_READ_MODE"))',
                '    runtime_write_mode: str = field(default_factory=lambda: require_value(env_str("RUNTIME_WRITE_MODE", "dual"), "RUNTIME_WRITE_MODE"))',
                '    rollout_drill_fault_mode: str = field(default_factory=lambda: require_value(env_str("ROLLOUT_DRILL_FAULT_MODE", "off"), "ROLLOUT_DRILL_FAULT_MODE"))',
                '    rollout_drill_fault_paths: str = field(default_factory=lambda: require_value(env_str("ROLLOUT_DRILL_FAULT_PATHS", "/ready"), "ROLLOUT_DRILL_FAULT_PATHS"))',
                '    rollout_drill_fault_status_code: int = field(default_factory=lambda: env_int("ROLLOUT_DRILL_FAULT_STATUS_CODE", 503))',
                '    rollout_drill_fault_delay_seconds: float = field(default_factory=lambda: env_float("ROLLOUT_DRILL_FAULT_DELAY_SECONDS", 3.0))',
            ]
        )
    if "internal-async-service" in patterns:
        lines.extend(
            [
                '    dapr_http_endpoint: str | None = field(default_factory=lambda: env_str("DAPR_HTTP_ENDPOINT"))',
                '    dapr_http_port: int = field(default_factory=lambda: env_int("DAPR_HTTP_PORT", 3500))',
                '    dapr_pubsub_name: str = field(default_factory=lambda: require_value(env_str("DAPR_PUBSUB_NAME", "async-events-pubsub"), "DAPR_PUBSUB_NAME"))',
                '    dapr_topic: str = field(default_factory=lambda: require_value(env_str("DAPR_TOPIC"), "DAPR_TOPIC"))',
                '    dapr_subscription_route: str = field(default_factory=lambda: require_value(env_str("DAPR_SUBSCRIPTION_ROUTE", "/internal/events/consume"), "DAPR_SUBSCRIPTION_ROUTE"))',
            ]
        )
    for env_name in extra_env:
        field_name = _field_name(env_name)
        lines.append(
            f'    {field_name}: str | None = field(default_factory=lambda: env_str("{env_name}"))'
        )
    lines.extend(
        [
            "",
            "    def __post_init__(self) -> None:",
            "        self.database_url = self.resolve_database_url(",
            "            database_url=self.database_url,",
            '            env_name="DATABASE_URL",',
            '            default_db_host="localhost",',
            "        )",
            "",
            "    @property",
            "    def required_database_url(self) -> str:",
            '        return require_value(self.database_url, "DATABASE_URL")',
        ]
    )
    for env_name in extra_env:
        field_name = _field_name(env_name)
        lines.extend(
            [
                "",
                "    @property",
                f"    def required_{field_name}(self) -> str:",
                f'        return require_value(self.{field_name}, "{env_name}")',
            ]
        )
    lines.extend(["", "", "settings = Settings()", ""])
    return "\n".join(lines)


def _render_job_config(
    database_pooling: str | None,
    extra_env: list[str],
    patterns: list[str],
) -> str:
    lines = [
        "from dataclasses import dataclass",
        "from dataclasses import field",
        "",
        "from infrastructure.config import env_str",
        "from infrastructure.config import load_env_file",
        "from infrastructure.config import require_value",
    ]
    if database_pooling is not None:
        lines.append("from infrastructure.config import PostgresRuntimeSettings")
    lines.extend(["", "", "load_env_file()", "", ""])
    base_class = "PostgresRuntimeSettings" if database_pooling is not None else "object"
    lines.append("@dataclass")
    lines.append(f"class Settings({base_class}):")
    has_fields = False
    if database_pooling is not None:
        has_fields = True
        lines.append(
            '    database_url: str | None = field(default_factory=lambda: env_str("DATABASE_URL"))'
        )
    if "export-job" in patterns:
        has_fields = True
        lines.append(
            '    data_export_output_dir: str | None = field(default_factory=lambda: env_str("DATA_EXPORT_OUTPUT_DIR"))'
        )
    for env_name in extra_env:
        has_fields = True
        field_name = _field_name(env_name)
        lines.append(
            f'    {field_name}: str | None = field(default_factory=lambda: env_str("{env_name}"))'
        )
    if not has_fields:
        lines.append("    pass")
    if database_pooling is not None:
        lines.extend(
            [
                "",
                "    def __post_init__(self) -> None:",
                "        self.database_url = self.resolve_database_url(",
                "            database_url=self.database_url,",
                '            env_name="DATABASE_URL",',
                "        )",
                "",
                "    @property",
                "    def required_database_url(self) -> str:",
                '        return require_value(self.database_url, "DATABASE_URL")',
            ]
        )
    if "export-job" in patterns:
        lines.extend(
            [
                "",
                "    @property",
                "    def required_data_export_output_dir(self) -> str:",
                '        return require_value(self.data_export_output_dir, "DATA_EXPORT_OUTPUT_DIR")',
            ]
        )
    for env_name in extra_env:
        field_name = _field_name(env_name)
        lines.extend(
            [
                "",
                "    @property",
                f"    def required_{field_name}(self) -> str:",
                f'        return require_value(self.{field_name}, "{env_name}")',
            ]
        )
    lines.extend(["", "", "settings = Settings()", ""])
    return "\n".join(lines)


def _render_service_main(
    module_name: str,
    patterns: list[str],
    service_port: int,
) -> str:
    edge_mode_block = ""
    edge_fault_block = ""
    edge_routes_block = ""
    if "edge-service" in patterns:
        edge_fault_block = textwrap.dedent(
            """\
            async def _rollout_fault_response(request: Request) -> Response | None:
                return await maybe_build_fault_response(
                    mode=settings.rollout_drill_fault_mode,
                    path=request.url.path,
                    configured_paths=settings.rollout_drill_fault_paths,
                    status_code=settings.rollout_drill_fault_status_code,
                    delay_seconds=settings.rollout_drill_fault_delay_seconds,
                    sleep=asyncio.sleep,
                )
            """
        ).rstrip()
        edge_mode_block = textwrap.dedent(
            """\
            _runtime_modes = {
                "read": settings.runtime_read_mode,
                "write": settings.runtime_write_mode,
            }
            """
        ).rstrip()
        edge_routes_block = textwrap.dedent(
            """\
            @app.get("/admin/read-mode")
            def get_read_mode() -> dict[str, str]:
                return {"mode": _runtime_modes["read"]}


            @app.post("/admin/read-mode")
            def set_read_mode(body: dict[str, str]) -> dict[str, str]:
                _runtime_modes["read"] = body.get("mode", _runtime_modes["read"])
                return {"mode": _runtime_modes["read"]}


            @app.get("/admin/write-mode")
            def get_write_mode() -> dict[str, str]:
                return {"mode": _runtime_modes["write"]}


            @app.post("/admin/write-mode")
            def set_write_mode(body: dict[str, str]) -> dict[str, str]:
                _runtime_modes["write"] = body.get("mode", _runtime_modes["write"])
                return {"mode": _runtime_modes["write"]}
            """
        ).rstrip()
    internal_async_block = ""
    if "internal-async-service" in patterns:
        internal_async_block = textwrap.dedent(
            """\
            @app.get("/dapr/subscribe")
            def dapr_subscribe() -> list[dict[str, str]]:
                return [
                    {
                        "pubsubname": settings.dapr_pubsub_name,
                        "topic": settings.dapr_topic,
                        "route": settings.dapr_subscription_route,
                    }
                ]


            @app.post("/internal/events/consume")
            def consume_event(payload: dict[str, object]) -> dict[str, object]:
                return {"status": "accepted", "payload": payload}
            """
        ).rstrip()

    imports = [
        "from __future__ import annotations",
        "",
        "import asyncio",
        "from contextlib import closing",
        "",
        "from fastapi import FastAPI, Request",
        "from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest",
        "from sqlalchemy import create_engine",
        "from sqlalchemy import text",
        "from starlette.responses import Response",
        "",
        f"from {module_name}.config import settings",
        "from infrastructure.http_health import database_readiness_response",
        "from infrastructure.http_health import health_payload",
    ]
    if "edge-service" in patterns:
        imports.append(
            "from infrastructure.http_faults import maybe_build_fault_response"
        )
    imports.append(
        "from infrastructure.http_observability import request_observability_middleware"
    )
    imports_block = "\n".join(imports)
    before_request = (
        "        before_request=_rollout_fault_response,\n"
        if "edge-service" in patterns
        else ""
    )
    body_sections = [
        edge_mode_block,
        "engine = create_engine(settings.required_database_url, future=True, pool_pre_ping=True)",
        'app = FastAPI(title="aws-sdlc-containers")',
        "",
        'REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests by method, route, and status code.", ["method", "route", "status_code"])',
        'REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency by method and route.", ["method", "route"])',
        edge_fault_block,
        textwrap.dedent(
            """\
            def _database_check() -> None:
                with closing(engine.connect()) as connection:
                    connection.execute(text("SELECT 1"))


            def _http_request_event(
                request: Request,
                response: Response,
                request_id: str,
                elapsed_seconds: float,
            ) -> dict[str, object]:
                return {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "route": getattr(request.scope.get("route"), "path", request.url.path),
                    "status_code": response.status_code,
                    "duration_ms": round(elapsed_seconds * 1000, 3),
                }


            app.middleware("http")(
                request_observability_middleware(
                    request_count=REQUEST_COUNT,
                    request_latency=REQUEST_LATENCY,
                    event_payload=_http_request_event,
            """
        ).rstrip()
        + ("\n" + before_request.rstrip() if before_request else "")
        + textwrap.dedent(
            """\
                )
            )


            @app.get("/health")
            def health() -> dict[str, str]:
                return health_payload()


            @app.get("/ready")
            def ready() -> dict[str, object] | Response:
                result = database_readiness_response(_database_check)
                if isinstance(result, Response):
                    return result
                return result


            @app.get("/metrics", include_in_schema=False)
            def metrics() -> Response:
                return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
            """
        ).rstrip(),
        edge_routes_block,
        internal_async_block,
    ]
    body = "\n\n".join(section for section in body_sections if section)
    return imports_block + "\n\n\n" + body + "\n"


def _render_job_main(
    module_name: str,
    workload_name: str,
    database_pooling: str | None,
    patterns: list[str],
) -> str:
    event_name = f"{workload_name}_succeeded"
    lines = [
        "from __future__ import annotations",
        "",
        "import json",
        "",
        f"from {module_name}.config import settings",
        "",
        "",
        f'JOB_NAME = "{workload_name}"',
        "",
        "",
        "def run_job() -> dict[str, object]:",
    ]
    if database_pooling is not None:
        lines.append("    _ = settings.required_database_url")
    lines.extend(
        [
            "    payload: dict[str, object] = {",
            f'        "event": "{event_name}",',
            '        "job_name": JOB_NAME,',
            '        "status": "succeeded",',
            "    }",
        ]
    )
    if "export-job" in patterns:
        lines.append(
            '    payload["output_dir"] = settings.required_data_export_output_dir'
        )
    lines.extend(
        [
            "    print(json.dumps(payload, sort_keys=True), flush=True)",
            "    return payload",
            "",
            "",
            "def main() -> None:",
            "    run_job()",
            "",
            "",
            'if __name__ == "__main__":',
            "    main()",
            "",
        ]
    )
    return "\n".join(lines)


def _render_pyproject(
    package_name: str,
    module_name: str,
    kind: str,
    traces_supported: bool,
    database_pooling: str | None,
) -> str:
    dependencies = [
        '"aws-sdlc-containers-application"',
        '"aws-sdlc-containers-infrastructure"',
        '"aws-sdlc-containers-domain"',
    ]
    if kind == "service":
        dependencies.extend(
            [
                '"fastapi>=0.111.0"',
                '"uvicorn>=0.29.0"',
                '"prometheus-client>=0.20.0"',
            ]
        )
        if database_pooling is not None:
            dependencies.extend(['"sqlalchemy>=2.0.30"', '"psycopg2-binary>=2.9.9"'])
        if traces_supported:
            dependencies.extend(
                [
                    '"opentelemetry-api>=1.39.0"',
                    '"opentelemetry-exporter-otlp-proto-http>=1.39.0"',
                    '"opentelemetry-instrumentation-fastapi>=0.60b0"',
                    '"opentelemetry-instrumentation-sqlalchemy>=0.60b0"',
                    '"opentelemetry-sdk>=1.39.0"',
                ]
            )
    lines = "\n".join(f"    {dependency}," for dependency in dependencies)
    return textwrap.dedent(
        f"""\
        [project]
        name = "{package_name}"
        version = "0.1.0"
        requires-python = ">=3.14"
        dependencies = [
        {lines}
        ]

        [build-system]
        requires = ["setuptools>=69"]
        build-backend = "setuptools.build_meta"

        [tool.setuptools]
        packages = ["{module_name}"]
        package-dir = {{ {module_name} = "." }}
        """
    )


def _render_service_test(module_name: str, patterns: list[str]) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        "import importlib",
        "",
        "from fastapi.testclient import TestClient",
        "",
        "",
        "def _load_main():",
        f'    return importlib.import_module("{module_name}.main")',
        "",
        "",
        "def test_operational_endpoints_are_available(monkeypatch) -> None:",
        "    main = _load_main()",
        '    monkeypatch.setattr(main, "_database_check", lambda: None)',
        "    client = TestClient(main.app)",
        "",
        '    health = client.get("/health")',
        '    ready = client.get("/ready")',
        '    metrics = client.get("/metrics")',
        "",
        "    assert health.status_code == 200",
        '    assert health.json() == {"status": "ok"}',
        "    assert ready.status_code == 200",
        '    assert ready.json()["status"] == "ready"',
        "    assert metrics.status_code == 200",
        '    assert "http_requests_total" in metrics.text',
        '    assert "http_request_duration_seconds" in metrics.text',
    ]
    if "edge-service" in patterns:
        lines.extend(
            [
                '    assert client.get("/admin/read-mode").json() == {"mode": "legacy"}',
                '    assert client.get("/admin/write-mode").json() == {"mode": "dual"}',
            ]
        )
    if "internal-async-service" in patterns:
        lines.extend(
            [
                '    subscribe = client.get("/dapr/subscribe")',
                "    assert subscribe.status_code == 200",
                "    subscriptions = subscribe.json()",
                '    assert subscriptions[0]["route"] == "/internal/events/consume"',
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _render_job_test(module_name: str, database_pooling: str | None) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        "import importlib",
        "",
        "",
        "def _load_main():",
        f'    return importlib.import_module("{module_name}.main")',
        "",
        "",
        "def test_run_job_emits_success_payload(monkeypatch) -> None:",
        "    main = _load_main()",
    ]
    if database_pooling is not None:
        lines.append(
            '    monkeypatch.setattr(main.settings, "database_url", "postgresql://postgres:postgres@db:5432/aws_sdlc_containers")'
        )
    lines.extend(
        [
            "    payload = main.run_job()",
            "",
            '    assert payload["status"] == "succeeded"',
            '    assert payload["job_name"] == main.JOB_NAME',
            '    assert payload["event"].endswith("_succeeded")',
            "",
        ]
    )
    return "\n".join(lines)


def _catalog_component_content(
    workload_name: str,
    owner: str,
    kind: str,
    description: str,
    use_cases: list[str],
    runtime_targets: list[str],
) -> str:
    component_type = "service" if kind == "service" else "job"
    lines = [
        "apiVersion: backstage.io/v1alpha1",
        "kind: Component",
        "metadata:",
        f"  name: {workload_name}",
        f"  description: {description}",
        "  tags:",
    ]
    lines.extend(f"    - {use_case}" for use_case in use_cases)
    lines.extend(
        [
            "spec:",
            f"  type: {component_type}",
            "  lifecycle: experimental",
            f"  owner: group:default/{owner}",
            "  system: aws-sdlc-containers",
            "  dependsOn:",
            "",
        ]
    )
    lines[-1:-1] = [
        f"    - resource:default/runtime-target-{runtime_target}"
        for runtime_target in runtime_targets
    ]
    return "\n".join(lines)


def _render_compose_service(
    workload_name: str,
    repository: str,
    kind: str,
    app_path: str,
    package_name: str,
    command: str,
    service_port: int | None,
    database_pooling: str | None,
    patterns: list[str],
    env_names: list[str],
) -> str:
    env_lines: list[str] = []
    depends_on_lines: list[str] = []
    if database_pooling == "transaction_pool":
        env_lines.append("      <<: *pooled_db_env")
        depends_on_lines.extend(
            [
                "      db:",
                "        condition: service_healthy",
                "      pgbouncer:",
                "        condition: service_healthy",
            ]
        )
    elif database_pooling == "direct":
        env_lines.append("      <<: *direct_db_env")
        depends_on_lines.extend(
            [
                "      db:",
                "        condition: service_healthy",
            ]
        )
    database_url = _database_url_placeholder(workload_name, database_pooling)
    if database_url is not None:
        env_lines.append(f"      DATABASE_URL: {database_url}")
    if "edge-service" in patterns:
        env_lines.extend(
            [
                "      OTEL_TRACES_ENABLED: ${OTEL_TRACES_ENABLED:-false}",
                "      OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: ${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:-http://tempo:4318/v1/traces}",
                f"      OTEL_SERVICE_NAME: aws-sdlc-containers-{repository}",
                "      OTEL_DEPLOYMENT_ENVIRONMENT: local",
                "      RUNTIME_READ_MODE: ${RUNTIME_READ_MODE:-legacy}",
                "      RUNTIME_WRITE_MODE: ${RUNTIME_WRITE_MODE:-dual}",
                "      ROLLOUT_DRILL_FAULT_MODE: ${ROLLOUT_DRILL_FAULT_MODE:-off}",
                "      ROLLOUT_DRILL_FAULT_PATHS: ${ROLLOUT_DRILL_FAULT_PATHS:-/ready}",
                "      ROLLOUT_DRILL_FAULT_STATUS_CODE: ${ROLLOUT_DRILL_FAULT_STATUS_CODE:-503}",
                "      ROLLOUT_DRILL_FAULT_DELAY_SECONDS: ${ROLLOUT_DRILL_FAULT_DELAY_SECONDS:-3}",
            ]
        )
    if "internal-async-service" in patterns:
        env_lines.extend(
            [
                "      DAPR_HTTP_ENDPOINT: ${DAPR_HTTP_ENDPOINT:-http://localhost:3500}",
                "      DAPR_HTTP_PORT: ${DAPR_HTTP_PORT:-3500}",
                "      DAPR_PUBSUB_NAME: ${DAPR_PUBSUB_NAME:-async-events-pubsub}",
                f"      DAPR_TOPIC: ${{DAPR_TOPIC:-{repository}-v1}}",
                "      DAPR_SUBSCRIPTION_ROUTE: ${DAPR_SUBSCRIPTION_ROUTE:-/internal/events/consume}",
            ]
        )
    for env_name in env_names:
        if env_name in {
            "DATABASE_URL",
            "DB_HOST",
            "DB_PORT",
            "DB_USER",
            "DB_NAME",
            "OTEL_TRACES_ENABLED",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            "OTEL_SERVICE_NAME",
            "OTEL_DEPLOYMENT_ENVIRONMENT",
            "RUNTIME_READ_MODE",
            "RUNTIME_WRITE_MODE",
            "ROLLOUT_DRILL_FAULT_MODE",
            "ROLLOUT_DRILL_FAULT_PATHS",
            "ROLLOUT_DRILL_FAULT_STATUS_CODE",
            "ROLLOUT_DRILL_FAULT_DELAY_SECONDS",
            "DAPR_HTTP_ENDPOINT",
            "DAPR_HTTP_PORT",
            "DAPR_PUBSUB_NAME",
            "DAPR_TOPIC",
            "DAPR_SUBSCRIPTION_ROUTE",
        }:
            continue
        env_lines.append(f"      {env_name}: ${{{env_name}:-}}")

    ports_block = ""
    if kind == "service" and service_port is not None:
        ports_block = textwrap.dedent(
            f"""\
                ports:
                  - "${{{_snake_to_upper(workload_name)}_PORT:-{service_port}}}:{service_port}"
            """
        ).rstrip()
    depends_on_block = ""
    if depends_on_lines:
        depends_on_block = "    depends_on:\n" + "\n".join(depends_on_lines)
    profiles_block = ""
    if kind == "job" and "export-job" in patterns:
        profiles_block = "    profiles:\n      - data"
    return (
        textwrap.dedent(
            f"""\

          {repository}:
            build:
              <<: *workload_build
              args:
                APP_PATH: {app_path}
                UV_PACKAGE: {package_name}
                WORKLOAD_CMD: {command}
            environment:
        """
        )
        + "\n".join(env_lines)
        + (f"\n{ports_block}" if ports_block else "")
        + (f"\n{depends_on_block}" if depends_on_block else "")
        + (f"\n{profiles_block}" if profiles_block else "")
        + "\n"
    )


def _update_compose(compose_path: Path, service_block: str) -> str:
    content = compose_path.read_text(encoding="utf-8")
    marker = "\nvolumes:\n"
    if marker not in content:
        raise ValueError(f"could not locate compose volumes block in {compose_path}")
    if service_block.lstrip() in content:
        raise ValueError("compose already contains the rendered workload service block")
    return content.replace(marker, service_block + marker, 1)


def _update_catalog_info(catalog_info_path: Path, target_path: str) -> str:
    content = catalog_info_path.read_text(encoding="utf-8")
    if f"    - {target_path}\n" in content:
        raise ValueError(f"catalog-info already references {target_path}")
    return content.rstrip() + f"\n    - {target_path}\n"


def _insert_sorted_workload(
    workloads_path: Path, workload_entry: dict[str, Any]
) -> dict[str, Any]:
    payload = _load_json(workloads_path)
    workloads = list(payload["workloads"])
    if any(item["name"] == workload_entry["name"] for item in workloads):
        raise ValueError(f"workload {workload_entry['name']!r} already exists")
    workloads.append(workload_entry)
    workloads.sort(key=lambda item: item["name"])
    payload["workloads"] = workloads
    return payload


def _insert_runtime_conformance(
    path: Path,
    workload_name: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    payload = _load_json(path)
    workloads = dict(payload["workloads"])
    if workload_name in workloads:
        raise ValueError(f"runtime conformance already contains {workload_name!r}")
    workloads[workload_name] = entry
    payload["workloads"] = {name: workloads[name] for name in sorted(workloads)}
    return payload


def _build_workload_entry(
    *,
    name: str,
    kind: str,
    patterns: list[str],
    use_cases: list[str],
    owner: str,
    supported_runtime_targets: list[str],
    admitted_runtime_targets: list[str],
    service_port: int | None,
    database_pooling: str | None,
    traces_supported: bool,
    extra_env: list[str],
    extra_secret: list[str],
) -> dict[str, Any]:
    repository = _snake_to_kebab(name)
    entry: dict[str, Any] = {
        "name": name,
        "kind": kind,
        "use_cases": use_cases,
        "owner": owner,
        "app_path": f"apps/{name}",
        "runtime": {
            "supported": supported_runtime_targets,
            "admitted": admitted_runtime_targets,
        },
    }
    if kind == "service":
        operational: dict[str, Any] = {
            "class": "edge-service"
            if "edge-service" in patterns
            else "internal-service"
        }
        if "edge-service" in patterns:
            operational["exposure"] = "public"
            entry["edge"] = {
                "hostname_label": repository,
                "hostname_label_convention": "explicit-label",
                "auth_mode": "static-bearer-token",
            }
            entry["verification"] = {
                "profile": "primary-edge-runtime-modes",
                "runtime_mode_endpoints": {
                    "read": "/admin/read-mode",
                    "write": "/admin/write-mode",
                },
            }
        else:
            operational["exposure"] = "internal"
            entry["dapr"] = {
                "app_id": repository,
                "scope": "pubsub",
                "pubsub_name": "async-events-pubsub",
                "topic": f"{repository}-v1",
                "subscription_route": "/internal/events/consume",
            }
        entry["operational"] = operational
        if service_port is None:
            raise ValueError("service workloads require --service-port")
        entry["service"] = {"port": service_port}
        entry["metrics"] = {
            "format": "prometheus",
            "required_names": [
                "http_requests_total",
                "http_request_duration_seconds",
            ],
        }
    else:
        operational = {
            "class": "scheduled-job" if "scheduled-job" in patterns else "operator-job"
        }
        if operational["class"] == "scheduled-job":
            operational["trigger"] = "schedule"
        else:
            operational["trigger"] = "manual"
        entry["operational"] = operational
        entry["job"] = {
            "idempotency": "run_id" if "scheduled-job" in patterns else "rerun-safe"
        }

    entry["image"] = {
        "repository": repository,
        "package": f"aws-sdlc-containers-{repository}",
        "command": (
            f"uvicorn {name}.main:app --host 0.0.0.0 --port {service_port}"
            if kind == "service"
            else f"python -m {name}.main"
        ),
    }
    entry["traces"] = {"supported": traces_supported}
    if database_pooling is not None:
        entry["database"] = {
            "semantics": "postgresql",
            "pooling": database_pooling,
        }
    env_names = (
        _service_env_names(patterns, traces_supported, extra_env)
        if kind == "service"
        else _job_env_names(database_pooling, patterns, extra_env)
    )
    entry["config"] = {
        "env": env_names,
        "secrets": (["DB_PASSWORD"] if database_pooling is not None else [])
        + extra_secret,
    }
    return entry


def _build_runtime_conformance_entry(
    *,
    name: str,
    kind: str,
    repository: str,
    database_pooling: str | None,
    patterns: list[str],
    traces_supported: bool,
    extra_env: list[str],
) -> dict[str, Any]:
    env: dict[str, str] = {}
    database_url = _database_url_fixture(database_pooling)
    if database_url is not None:
        env["DATABASE_URL"] = database_url
    if kind == "service":
        if traces_supported:
            env["OTEL_TRACES_ENABLED"] = "false"
            env["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = (
                "http://127.0.0.1:4318/v1/traces"
            )
            env["OTEL_SERVICE_NAME"] = f"aws-sdlc-containers-{repository}-conformance"
            env["OTEL_DEPLOYMENT_ENVIRONMENT"] = "conformance"
        if "edge-service" in patterns:
            env["RUNTIME_READ_MODE"] = "legacy"
            env["RUNTIME_WRITE_MODE"] = "dual"
            env["ROLLOUT_DRILL_FAULT_MODE"] = "off"
            env["ROLLOUT_DRILL_FAULT_PATHS"] = "/ready"
            env["ROLLOUT_DRILL_FAULT_STATUS_CODE"] = "503"
            env["ROLLOUT_DRILL_FAULT_DELAY_SECONDS"] = "3"
        if "internal-async-service" in patterns:
            env["DAPR_HTTP_ENDPOINT"] = "http://127.0.0.1:3500"
            env["DAPR_HTTP_PORT"] = "3500"
            env["DAPR_PUBSUB_NAME"] = "async-events-pubsub"
            env["DAPR_TOPIC"] = f"{repository}-v1"
            env["DAPR_SUBSCRIPTION_ROUTE"] = "/internal/events/consume"
        for env_name in extra_env:
            env[env_name] = ""
        return {
            "startup_timeout_seconds": 60,
            "env": env,
            "expected_log_event": "http_request",
            "expected_log_fields": ["event", "request_id", "route", "status_code"],
        }

    if "export-job" in patterns:
        env["DATA_EXPORT_OUTPUT_DIR"] = "/exports"
    for env_name in extra_env:
        env[env_name] = ""
    return {
        "timeout_seconds": 60,
        "env": env,
        "expected_success_event": f"{name}_succeeded",
        "expected_log_fields": ["event", "job_name", "status"],
    }


def build_plan(args: argparse.Namespace) -> WorkloadScaffoldPlan:
    name = str(args.name)
    _validate_name(name)
    use_cases = list(dict.fromkeys(args.use_case))
    _validate_use_cases(use_cases)
    patterns = _normalized_patterns(list(dict.fromkeys(args.pattern)))
    kind, operational_class = _resolve_kind_and_class(patterns)
    database_pooling = args.database_pooling
    if database_pooling == "none":
        database_pooling = None
    if database_pooling is None:
        database_pooling = _default_database_pooling(patterns, kind)
    traces_supported = (
        bool(args.traces_supported)
        if args.traces_supported is not None
        else _default_traces_supported(patterns)
    )
    supported_runtime_targets, admitted_runtime_targets = _resolved_runtime_targets(
        list(dict.fromkeys(args.supported_runtime)),
        list(dict.fromkeys(args.admitted_runtime)),
    )
    repository = _snake_to_kebab(name)
    workload_entry = _build_workload_entry(
        name=name,
        kind=kind,
        patterns=patterns,
        use_cases=use_cases,
        owner=str(args.owner),
        supported_runtime_targets=supported_runtime_targets,
        admitted_runtime_targets=admitted_runtime_targets,
        service_port=args.service_port,
        database_pooling=database_pooling,
        traces_supported=traces_supported,
        extra_env=list(dict.fromkeys(args.extra_env)),
        extra_secret=list(dict.fromkeys(args.extra_secret)),
    )
    runtime_entry = _build_runtime_conformance_entry(
        name=name,
        kind=kind,
        repository=repository,
        database_pooling=database_pooling,
        patterns=patterns,
        traces_supported=traces_supported,
        extra_env=list(dict.fromkeys(args.extra_env)),
    )
    package_name = str(workload_entry["image"]["package"])
    command = str(workload_entry["image"]["command"])
    env_names = list(workload_entry["config"]["env"])
    files = [
        RenderedFile(
            path=f"apps/{name}/config.py",
            mode="create",
            content=(
                _render_service_config(
                    name,
                    patterns,
                    traces_supported,
                    list(dict.fromkeys(args.extra_env)),
                )
                if kind == "service"
                else _render_job_config(
                    database_pooling,
                    list(dict.fromkeys(args.extra_env)),
                    patterns,
                )
            ),
        ),
        RenderedFile(
            path=f"apps/{name}/main.py",
            mode="create",
            content=(
                _render_service_main(name, patterns, int(args.service_port))
                if kind == "service"
                else _render_job_main(name, name, database_pooling, patterns)
            ),
        ),
        RenderedFile(
            path=f"apps/{name}/pyproject.toml",
            mode="create",
            content=_render_pyproject(
                package_name,
                name,
                kind,
                traces_supported,
                database_pooling,
            ),
        ),
        RenderedFile(
            path=f"tests/apps/{name}/test_{name}.py",
            mode="create",
            content=(
                _render_service_test(name, patterns)
                if kind == "service"
                else _render_job_test(name, database_pooling)
            ),
        ),
        RenderedFile(
            path=f"catalog/{repository}-component.yaml",
            mode="create",
            content=_catalog_component_content(
                name,
                str(args.owner),
                kind,
                args.description or _description(name, patterns),
                use_cases,
                supported_runtime_targets,
            ),
        ),
    ]
    files.append(
        RenderedFile(
            path="compose.yaml",
            mode="update",
            content=_render_compose_service(
                workload_name=name,
                repository=repository,
                kind=kind,
                app_path=f"apps/{name}",
                package_name=package_name,
                command=command,
                service_port=args.service_port,
                database_pooling=database_pooling,
                patterns=patterns,
                env_names=env_names,
            ),
        )
    )
    files.append(
        RenderedFile(
            path="catalog-info.yaml",
            mode="update",
            content=f"./catalog/{repository}-component.yaml",
        )
    )
    return WorkloadScaffoldPlan(
        workload_name=name,
        patterns=patterns,
        use_cases=use_cases,
        kind=kind,
        operational_class=operational_class,
        files=files,
        workload_entry=workload_entry,
        runtime_conformance_entry=runtime_entry,
    )


def apply_plan(root: Path, plan: WorkloadScaffoldPlan) -> None:
    for rendered in plan.files:
        path = root / rendered.path
        path.parent.mkdir(parents=True, exist_ok=True)
        if rendered.mode == "create":
            if path.exists():
                raise ValueError(f"refusing to overwrite existing file {rendered.path}")
            path.write_text(rendered.content, encoding="utf-8")
            continue
        if rendered.path == "compose.yaml":
            updated = _update_compose(path, rendered.content)
            path.write_text(updated, encoding="utf-8")
            continue
        if rendered.path == "catalog-info.yaml":
            updated = _update_catalog_info(path, rendered.content)
            path.write_text(updated, encoding="utf-8")
            continue
        raise ValueError(f"unknown update target {rendered.path}")

    workloads_path = root / "platform" / "workloads.json"
    runtime_conformance_path = root / "platform" / "runtime-conformance.json"
    workloads_payload = _insert_sorted_workload(workloads_path, plan.workload_entry)
    runtime_payload = _insert_runtime_conformance(
        runtime_conformance_path,
        plan.workload_name,
        plan.runtime_conformance_entry,
    )
    _write_json(workloads_path, workloads_payload)
    _write_json(runtime_conformance_path, runtime_payload)


def _plan_preview(plan: WorkloadScaffoldPlan) -> dict[str, Any]:
    return {
        "workload_name": plan.workload_name,
        "patterns": plan.patterns,
        "use_cases": plan.use_cases,
        "kind": plan.kind,
        "operational_class": plan.operational_class,
        "files": [
            {"path": rendered.path, "mode": rendered.mode} for rendered in plan.files
        ],
        "workload_entry": plan.workload_entry,
        "runtime_conformance_entry": plan.runtime_conformance_entry,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scaffold a standardized workload host and stable-center metadata."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--name", required=True)
    parser.add_argument("--pattern", action="append", required=True)
    parser.add_argument("--use-case", action="append", required=True)
    parser.add_argument("--owner", default="platform-engineering")
    parser.add_argument("--service-port", type=int)
    parser.add_argument(
        "--supported-runtime",
        action="append",
        default=[],
        choices=SCAFFOLD_RUNTIME_TARGETS,
        help="Add a supported runtime target. local-compose is always included.",
    )
    parser.add_argument(
        "--admitted-runtime",
        action="append",
        default=[],
        choices=["aws-ecs"],
        help="Add a reviewed runtime admission target such as aws-ecs.",
    )
    parser.add_argument(
        "--database-pooling",
        choices=["none", "direct", "transaction_pool"],
        default=None,
    )
    parser.add_argument(
        "--traces-supported",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument("--extra-env", action="append", default=[])
    parser.add_argument("--extra-secret", action="append", default=[])
    parser.add_argument("--description")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write files instead of printing a preview plan.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        plan = build_plan(args)
        if args.apply:
            apply_plan(args.root, plan)
            print(
                json.dumps(
                    {
                        "status": "applied",
                        "workload_name": plan.workload_name,
                        "files_written": [rendered.path for rendered in plan.files],
                    },
                    indent=2,
                )
            )
            return 0
        print(json.dumps(_plan_preview(plan), indent=2))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
