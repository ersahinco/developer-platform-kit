#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.workload_read_model import monorepo_capability_profile  # noqa: E402
from scripts.platform.workload_read_model import (  # noqa: E402
    required_capabilities_for_workload,
)

RUNTIME_DEFAULTS_PATH = ROOT / "platform" / "runtime-defaults.json"
VALID_KINDS = {"service", "job"}
SERVICE_CLASSES = {"edge-service", "internal-service"}
JOB_CLASSES = {"operator-job", "scheduled-job"}
VALID_TRIGGERS = {"manual", "schedule"}

KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
AWS_ACCOUNT_ID = re.compile(r"\b\d{12}\b")
AWS_ARN = re.compile(r"\barn:aws[a-z-]*:", re.IGNORECASE)
AWS_HOST = re.compile(r"\b[a-z0-9.-]+\.amazonaws\.com\b", re.IGNORECASE)
URL = re.compile(r"\b[a-z][a-z0-9+.-]*://", re.IGNORECASE)
FQDN = re.compile(
    r"\b(?!(?:python|uvicorn|gunicorn|pytest|alembic)\b)"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\b",
    re.IGNORECASE,
)

FORBIDDEN_KEY_PARTS = {
    "account_id",
    "aws_account",
    "azure_devops",
    "bucket",
    "bucket_arn",
    "bucket_name",
    "ci",
    "ci_pipeline",
    "cluster",
    "database_host",
    "database_url",
    "datadog",
    "desired_count",
    "dns",
    "ecs",
    "elastic",
    "entra",
    "fqdn",
    "hosted_zone",
    "iam",
    "jenkins",
    "jwt_provider",
    "kong",
    "log_group",
    "newrelic",
    "oidc_provider",
    "okta",
    "opa",
    "observability",
    "pipeline",
    "policy_arn",
    "queue_arn",
    "queue_url",
    "role_arn",
    "root_domain",
    "rule_arn",
    "rule_name",
    "s3_bucket",
    "schedule_expression",
    "scheduler_rule",
    "service_name",
    "splunk",
    "sns_topic",
    "sqs_queue",
    "subnet",
    "target_group",
    "task_definition",
    "topic_arn",
    "topic_url",
    "terraform",
    "workflow",
}

FORBIDDEN_VALUE_PATTERNS = (
    ("AWS account id", AWS_ACCOUNT_ID),
    ("AWS ARN", AWS_ARN),
    ("AWS endpoint", AWS_HOST),
    ("URL or connection string", URL),
    ("FQDN", FQDN),
)

OBSERVABILITY_BACKEND_NAMES = ("datadog", "splunk")
RUNTIME_TOOL_NAMES = (
    "auth0",
    "cedar",
    "datadog",
    "elastic",
    "entra",
    "kong",
    "new relic",
    "newrelic",
    "okta",
    "opa",
    "splunk",
)
OBSERVABILITY_CONFIG_PREFIXES = ("DD_", "DATADOG_", "SPLUNK_")


@dataclass(frozen=True)
class FitResult:
    area: str
    status: str
    message: str
    details: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeLeak:
    path: str
    reason: str


KEEP_AS_WORKLOAD_CONTRACT = (
    "owner",
    "use_cases",
    "kind and operational.class",
    "service port or job idempotency",
    "config env/secrets",
    "database semantics",
    "Prometheus metric identity",
    "structured workload events",
)


def _ok(area: str, message: str) -> FitResult:
    return FitResult(area=area, status="ok", message=message)


def _fail(
    area: str,
    message: str,
    *,
    details: dict[str, list[str]] | None = None,
) -> FitResult:
    return FitResult(area=area, status="fail", message=message, details=details or {})


def _path_join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _walk(value: Any, path: str = "") -> list[tuple[str, Any]]:
    rows = [(path, value)]
    if isinstance(value, dict):
        for key, nested in value.items():
            rows.extend(_walk(nested, _path_join(path, str(key))))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            rows.extend(_walk(nested, f"{path}[{index}]"))
    return rows


def _get_path(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _stable_center_fields(candidate: dict[str, Any]) -> FitResult:
    required = [
        "name",
        "kind",
        "owner",
        "use_cases",
        "runtime.supported",
        "runtime.admitted",
        "operational.class",
        "image.repository",
        "image.package",
        "image.command",
        "config.env",
        "config.secrets",
        "traces.supported",
    ]
    missing = [path for path in required if _get_path(candidate, path) is None]
    if missing:
        return _fail(
            "stable_center_fields",
            "missing stable-center fields: " + ", ".join(missing),
        )

    failures: list[str] = []
    for path in ["name", "owner", "image.repository", "image.package", "image.command"]:
        if not _is_non_empty_string(_get_path(candidate, path)):
            failures.append(f"{path} must be a non-empty string")
    if _is_non_empty_string(candidate.get("name")) and not re.fullmatch(
        r"[a-z0-9_]+", str(candidate["name"])
    ):
        failures.append("name must use lowercase snake_case")
    if _is_non_empty_string(candidate.get("owner")) and not KEBAB_CASE.fullmatch(
        str(candidate["owner"])
    ):
        failures.append("owner must use lowercase kebab-case")
    if not _is_string_list(_get_path(candidate, "use_cases")):
        failures.append("use_cases must be a string array")
    elif not candidate["use_cases"]:
        failures.append("use_cases must not be empty")
    elif any(not KEBAB_CASE.fullmatch(value) for value in candidate["use_cases"]):
        failures.append("use_cases entries must use lowercase kebab-case")
    for path in ["config.env", "config.secrets"]:
        values = _get_path(candidate, path)
        if not _is_string_list(values):
            failures.append(f"{path} must be a string array")
        elif any(not ENV_NAME.fullmatch(value) for value in values):
            failures.append(f"{path} entries must look like environment variable names")
    if _get_path(candidate, "traces.supported") not in {True, False}:
        failures.append("traces.supported must be boolean")

    if failures:
        return _fail("stable_center_fields", "; ".join(failures))
    return _ok("stable_center_fields", "candidate declares the stable workload shape")


def _service_or_job_shape(candidate: dict[str, Any]) -> FitResult:
    kind = candidate.get("kind")
    operational = candidate.get("operational", {})
    operational_class = (
        operational.get("class") if isinstance(operational, dict) else None
    )
    failures: list[str] = []

    if kind not in VALID_KINDS:
        failures.append("kind must be service or job")
    elif kind == "service":
        if operational_class not in SERVICE_CLASSES:
            failures.append(
                "service operational.class must be edge-service or internal-service"
            )
        port = _get_path(candidate, "service.port")
        if not isinstance(port, int) or port <= 0:
            failures.append("service workloads must declare a positive service.port")
        required_names = _get_path(candidate, "metrics.required_names")
        if not _is_string_list(required_names) or "workload_info" not in required_names:
            failures.append(
                "service workloads must declare metrics.required_names including workload_info"
            )
        if operational_class == "edge-service":
            edge = candidate.get("edge")
            if not isinstance(edge, dict):
                failures.append("edge-service workloads must declare edge metadata")
            elif not all(
                _is_non_empty_string(edge.get(key))
                for key in ["hostname_label", "hostname_label_convention", "auth_mode"]
            ):
                failures.append(
                    "edge-service edge metadata must include hostname_label, "
                    "hostname_label_convention, and auth_mode"
                )
    elif kind == "job":
        if operational_class not in JOB_CLASSES:
            failures.append(
                "job operational.class must be operator-job or scheduled-job"
            )
        trigger = operational.get("trigger") if isinstance(operational, dict) else None
        if trigger not in VALID_TRIGGERS:
            failures.append("job workloads must declare operational.trigger")
        idempotency = _get_path(candidate, "job.idempotency")
        if not _is_non_empty_string(idempotency):
            failures.append("job workloads must declare job.idempotency")

    if failures:
        return _fail("workload_shape", "; ".join(failures))
    return _ok("workload_shape", "kind and operational class match the contract")


def _runtime_scope(candidate: dict[str, Any]) -> FitResult:
    supported = _get_path(candidate, "runtime.supported")
    admitted = _get_path(candidate, "runtime.admitted")
    known_runtime_targets = _known_runtime_targets()
    failures: list[str] = []

    if not _is_string_list(supported) or not supported:
        failures.append("runtime.supported must be a non-empty string array")
        supported_set: set[str] = set()
    else:
        supported_set = set(supported)
        unknown_supported = sorted(supported_set - known_runtime_targets)
        if unknown_supported:
            failures.append(
                "runtime.supported contains unknown targets: "
                + ", ".join(unknown_supported)
            )

    if not _is_string_list(admitted):
        failures.append("runtime.admitted must be a string array")
        admitted_set: set[str] = set()
    else:
        admitted_set = set(admitted)
        unknown_admitted = sorted(admitted_set - known_runtime_targets)
        if unknown_admitted:
            failures.append(
                "runtime.admitted contains unknown targets: "
                + ", ".join(unknown_admitted)
            )
        missing_support = sorted(admitted_set - supported_set)
        if missing_support:
            failures.append(
                "runtime.admitted must be a subset of runtime.supported: "
                + ", ".join(missing_support)
            )

    if failures:
        return _fail("runtime_scope", "; ".join(failures))
    return _ok("runtime_scope", "runtime support and admission use known targets")


def _key_leaks(candidate: dict[str, Any]) -> list[EdgeLeak]:
    leaks: list[EdgeLeak] = []
    for path, value in _walk(candidate):
        if not isinstance(value, dict):
            continue
        for key in value:
            normalized = str(key).lower().replace("-", "_")
            if _forbidden_key(normalized):
                forbidden_path = _path_join(path, str(key))
                leaks.extend(
                    EdgeLeak(
                        path=leaf_path,
                        reason="is platform-edge wiring",
                    )
                    for leaf_path in _removal_paths(value[key], forbidden_path)
                )
    return leaks


def _removal_paths(value: Any, path: str) -> list[str]:
    if isinstance(value, dict) and value:
        return [
            leaf
            for key, nested in value.items()
            for leaf in _removal_paths(nested, _path_join(path, str(key)))
        ]
    if isinstance(value, list) and value:
        return [
            leaf
            for index, nested in enumerate(value)
            for leaf in _removal_paths(nested, f"{path}[{index}]")
        ]
    return [path]


def _forbidden_key(normalized: str) -> bool:
    return any(
        normalized == part
        or normalized.startswith(f"{part}_")
        or normalized.endswith(f"_{part}")
        for part in FORBIDDEN_KEY_PARTS
    )


def _value_leaks(candidate: dict[str, Any]) -> list[EdgeLeak]:
    leaks: list[EdgeLeak] = []
    for path, value in _walk(candidate):
        if not isinstance(value, str):
            continue
        lower_value = value.lower()
        if path.endswith("image.command"):
            patterns = [
                (label, pattern)
                for label, pattern in FORBIDDEN_VALUE_PATTERNS
                if label not in {"URL or connection string", "FQDN"}
            ]
        else:
            patterns = FORBIDDEN_VALUE_PATTERNS
        for label, pattern in patterns:
            if pattern.search(value):
                leaks.append(EdgeLeak(path=path, reason=f"contains {label}"))
                break
        if any(name in lower_value for name in RUNTIME_TOOL_NAMES):
            leaks.append(
                EdgeLeak(
                    path=path,
                    reason="mentions runtime tool wiring",
                )
            )
        if "jenkins" in lower_value or "azure devops" in lower_value:
            leaks.append(EdgeLeak(path=path, reason="mentions CI system wiring"))
    return leaks


def _config_backend_leaks(candidate: dict[str, Any]) -> list[EdgeLeak]:
    leaks: list[EdgeLeak] = []
    for path in ["config.env", "config.secrets"]:
        values = _get_path(candidate, path)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            if value.startswith(OBSERVABILITY_CONFIG_PREFIXES):
                leaks.append(
                    EdgeLeak(
                        path=f"{path}.{value}",
                        reason="contains backend-specific observability config",
                    )
                )
    return leaks


def _platform_edge_boundary(candidate: dict[str, Any]) -> FitResult:
    leaks = (
        _key_leaks(candidate)
        + _value_leaks(candidate)
        + _config_backend_leaks(candidate)
    )
    if leaks:
        remove_paths = sorted({leak.path for leak in leaks})
        messages = sorted({f"{leak.path} {leak.reason}" for leak in leaks})
        return _fail(
            "platform_edge_boundary",
            "move platform-edge details out of the workload contract: "
            + "; ".join(messages),
            details={"remove_from_stable_center": remove_paths},
        )
    return _ok(
        "platform_edge_boundary",
        "account, DNS, IAM, CI, logs, and backend routing stay outside the contract",
    )


def _database_intent(candidate: dict[str, Any]) -> FitResult:
    database = candidate.get("database")
    if database is None:
        return _ok("database_intent", "candidate does not declare database capability")
    if not isinstance(database, dict):
        return _fail("database_intent", "database must be an object when declared")

    allowed_keys = {"semantics", "pooling"}
    extra_keys = sorted(set(database) - allowed_keys)
    failures: list[str] = []
    if extra_keys:
        failures.append(
            "database must only declare portable semantics and pooling; extra keys: "
            + ", ".join(extra_keys)
        )
    if database.get("semantics") != "postgresql":
        failures.append("database.semantics must be postgresql")
    if database.get("pooling") not in {"direct", "transaction_pool"}:
        failures.append("database.pooling must be direct or transaction_pool")

    if failures:
        return _fail("database_intent", "; ".join(failures))
    return _ok(
        "database_intent",
        "database declaration is PostgreSQL intent, not managed database wiring",
    )


def _observability_contract(candidate: dict[str, Any]) -> FitResult:
    failures: list[str] = []
    if candidate.get("kind") == "service":
        required_names = _get_path(candidate, "metrics.required_names")
        if not _is_string_list(required_names) or "workload_info" not in required_names:
            failures.append("services must expose Prometheus workload_info metrics")
        if _get_path(candidate, "metrics.format") != "prometheus":
            failures.append("services must declare metrics.format as prometheus")
    if candidate.get("kind") == "job":
        idempotency = _get_path(candidate, "job.idempotency")
        if not _is_non_empty_string(idempotency):
            failures.append("jobs must declare idempotency for terminal event evidence")
    config_names = [
        value
        for path in ["config.env", "config.secrets"]
        for value in (_get_path(candidate, path) or [])
        if isinstance(value, str)
    ]
    backend_names = [
        value
        for value in config_names
        if value.startswith(OBSERVABILITY_CONFIG_PREFIXES)
    ]
    if backend_names:
        failures.append(
            "Datadog/Splunk config belongs at the platform edge: "
            + ", ".join(backend_names)
        )

    if failures:
        return _fail("observability_contract", "; ".join(failures))
    return _ok(
        "observability_contract",
        "telemetry can route to Datadog/Splunk if workload fields are preserved",
    )


def _capability_profile_fit(candidate: dict[str, Any]) -> FitResult:
    requested = sorted(required_capabilities_for_workload(candidate))
    profile = monorepo_capability_profile()
    available = sorted(
        {
            row["capability"]
            for row in profile["infra_capabilities"]
            if isinstance(row, dict) and isinstance(row.get("capability"), str)
        }
    )
    missing = sorted(set(requested) - set(available))
    details = {
        "requested_profile_capabilities": requested,
        "missing_profile_capabilities": missing,
    }
    if missing:
        return _fail(
            "capability_profile_fit",
            "candidate asks for capabilities outside the current monorepo profile: "
            + ", ".join(missing),
            details=details,
        )
    return FitResult(
        area="capability_profile_fit",
        status="ok",
        message="candidate asks for current monorepo profile capabilities",
        details=details,
    )


def evaluate_candidate(candidate: dict[str, Any]) -> list[FitResult]:
    return [
        _stable_center_fields(candidate),
        _service_or_job_shape(candidate),
        _runtime_scope(candidate),
        _capability_profile_fit(candidate),
        _platform_edge_boundary(candidate),
        _database_intent(candidate),
        _observability_contract(candidate),
    ]


def _load_runtime_defaults() -> dict[str, Any]:
    data = json.loads(RUNTIME_DEFAULTS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("platform/runtime-defaults.json must be a JSON object")
    return data


def _known_runtime_targets() -> set[str]:
    runtime_defaults = _load_runtime_defaults()
    targets = runtime_defaults.get("runtime_targets", {})
    if not isinstance(targets, dict):
        return set()
    return {
        runtime_target
        for runtime_target, profile in targets.items()
        if isinstance(runtime_target, str)
        and isinstance(profile, dict)
        and profile.get("status") == "active"
    }


def _runtime_default_lines(candidate: dict[str, Any]) -> list[str]:
    runtime_defaults = _load_runtime_defaults()
    targets = runtime_defaults.get("runtime_targets", {})
    if not isinstance(targets, dict):
        return []
    supported = _get_path(candidate, "runtime.supported")
    if not isinstance(supported, list):
        return []

    lines: list[str] = []
    for runtime_target in supported:
        if not isinstance(runtime_target, str):
            continue
        profile = targets.get(runtime_target)
        if not isinstance(profile, dict):
            continue
        defaults = profile.get("defaults", {})
        if not isinstance(defaults, dict):
            continue
        authn = _get_path(defaults, "authn.default")
        secrets = _get_path(defaults, "secrets.default")
        observability = _get_path(defaults, "observability.default")
        network = _get_path(defaults, "network.default")
        values = [
            f"authn={authn}",
            f"secrets={secrets}",
            f"observability={observability}",
            f"network={network}",
        ]
        lines.append(f"{runtime_target}: " + "; ".join(values))
    return lines


def _load_candidate(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"candidate file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"candidate file is not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise SystemExit("candidate JSON must be one workload object")
    return document


def _print_table(results: list[FitResult], candidate: dict[str, Any]) -> None:
    fits = not any(result.status == "fail" for result in results)
    print(f"fit: {'yes' if fits else 'no'}")
    print("\t".join(["area", "status", "message"]))
    for result in results:
        print("\t".join([result.area, result.status, result.message]))
    if fits:
        runtime_lines = _runtime_default_lines(candidate)
        if runtime_lines:
            print("runtime defaults:")
            for line in runtime_lines:
                print(f"- {line}")
        profile_fit = next(
            result for result in results if result.area == "capability_profile_fit"
        )
        requested = profile_fit.details.get("requested_profile_capabilities", [])
        if requested:
            print("capability profile:")
            print("- requested: " + ", ".join(requested))
        print("next make workload-readiness")
        print("next make platform-doctor")
        print("next add to platform/workloads.json only after local proof exists")
        return

    remove_paths = sorted(
        {
            path
            for result in results
            for path in result.details.get("remove_from_stable_center", [])
        }
    )
    if remove_paths:
        print("remove from stable center:")
        for path in remove_paths:
            print(f"- {path}")
    print("keep as workload contract:")
    for item in KEEP_AS_WORKLOAD_CONTRACT:
        print(f"- {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a draft externally operated workload against the workload "
            "contract boundary before adding it to platform/workloads.json."
        )
    )
    parser.add_argument(
        "--candidate",
        default=os.environ.get("WORKLOAD_CANDIDATE"),
        help="Path to a draft workload JSON object. Defaults to WORKLOAD_CANDIDATE.",
    )
    parser.add_argument("--format", choices=["table", "json"], default="table")
    args = parser.parse_args(argv)

    if not args.candidate:
        print(
            "set WORKLOAD_CANDIDATE=<path> or pass --candidate <path>",
            file=sys.stderr,
        )
        return 2

    candidate = _load_candidate(Path(args.candidate))
    results = evaluate_candidate(candidate)
    if args.format == "json":
        print(json.dumps([asdict(result) for result in results], sort_keys=True))
    else:
        _print_table(results, candidate)
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
