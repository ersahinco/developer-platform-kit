"""
verify_observability_delivery.py — Check deployed log delivery contracts.

The live checks focus on log delivery. CloudWatch is checked through AWS CLI.
Loki is checked only when LOKI_URL is set, so the same script works with the
local observability profile or any reachable Loki endpoint.

Usage:
    python scripts/observability/verify_observability_delivery.py

Environment:
    AWS_REGION                       Default: eu-central-1
    STACK_NAME                       Default: aws-sdlc-containers
    CLOUDWATCH_LOG_FRESHNESS_SECONDS Default: 86400
    CLOUDWATCH_FRESH_LOG_GROUPS      Optional comma-separated group names
    LOKI_URL                         Optional, for example http://127.0.0.1:3100
    LOKI_FRESHNESS_SECONDS           Default: CLOUDWATCH_LOG_FRESHNESS_SECONDS
    LOKI_LABEL_LOOKBACK_SECONDS      Default: 2592000
    LOKI_FRESH_LOG_GROUPS            Optional comma-separated group suffixes
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_SUPPORT_LOG_GROUP_SUFFIXES = ["liquibase", "pgbouncer"]
OPTIONAL_SUPPORT_LOG_GROUP_SUFFIXES = ["adot"]
DEFAULT_ALLOWED_EXTRA_STACK_LOG_GROUP_SUFFIXES = [
    "firelens",
    "grafana",
    "loki",
    "prometheus",
    "tempo",
]
DEFAULT_FRESH_LOG_GROUP_SUFFIXES = ["app", "pgbouncer"]
DEFAULT_FRESH_LOKI_LOG_GROUP_SUFFIXES = ["app"]


@lru_cache(maxsize=1)
def _workload_log_group_suffixes() -> list[str]:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    return [workload["image"]["repository"] for workload in contract["workloads"]]


def _expected_log_group_suffixes() -> list[str]:
    return [*_workload_log_group_suffixes(), *REQUIRED_SUPPORT_LOG_GROUP_SUFFIXES]


def _known_log_group_suffixes() -> list[str]:
    allowed_extras = _csv_env(
        "CLOUDWATCH_ALLOWED_EXTRA_LOG_GROUPS",
        DEFAULT_ALLOWED_EXTRA_STACK_LOG_GROUP_SUFFIXES,
    )
    return [
        *_expected_log_group_suffixes(),
        *OPTIONAL_SUPPORT_LOG_GROUP_SUFFIXES,
        *allowed_extras,
    ]


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    message: str


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _aws_json(args: list[str], region: str) -> dict[str, Any]:
    command = ["aws", *args, "--region", region, "--output", "json"]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _expected_log_group_names(stack_name: str) -> list[str]:
    return [f"/ecs/{stack_name}/{suffix}" for suffix in _expected_log_group_suffixes()]


def _expected_loki_log_group_names(stack_name: str) -> list[str]:
    return [f"/ecs/{stack_name}/{suffix}" for suffix in _expected_log_group_suffixes()]


def _check_cloudwatch_log_inventory(stack_name: str, region: str) -> list[CheckResult]:
    prefix = f"/ecs/{stack_name}"
    expected = set(_expected_log_group_names(stack_name))
    known = {f"/ecs/{stack_name}/{suffix}" for suffix in _known_log_group_suffixes()}
    optional = {
        f"/ecs/{stack_name}/{suffix}" for suffix in OPTIONAL_SUPPORT_LOG_GROUP_SUFFIXES
    }

    try:
        response = _aws_json(
            [
                "logs",
                "describe-log-groups",
                "--log-group-name-prefix",
                prefix,
            ],
            region,
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return [CheckResult(False, f"CloudWatch log group inventory failed: {exc}")]

    groups = {
        group.get("logGroupName"): group
        for group in response.get("logGroups", [])
        if isinstance(group.get("logGroupName"), str)
    }
    actual = set(groups)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - known)
    optional_present = sorted(actual & optional)
    optional_missing = sorted(optional - actual)

    results = [
        CheckResult(
            not missing,
            "CloudWatch expected log groups present"
            if not missing
            else f"CloudWatch missing log groups: {', '.join(missing)}",
        ),
        CheckResult(
            not unexpected,
            "CloudWatch has no unexpected stack log groups"
            if not unexpected
            else f"CloudWatch unexpected stack log groups: {', '.join(unexpected)}",
        ),
        CheckResult(
            True,
            "CloudWatch optional support log groups present: "
            + (", ".join(optional_present) if optional_present else "none"),
        ),
        CheckResult(
            True,
            "CloudWatch optional support log groups absent: "
            + (", ".join(optional_missing) if optional_missing else "none"),
        ),
    ]

    for name in sorted(expected & actual):
        retention_days = groups[name].get("retentionInDays")
        results.append(
            CheckResult(
                isinstance(retention_days, int) and retention_days > 0,
                f"{name} retention={retention_days!r} days",
            )
        )

    return results


def _latest_cloudwatch_event_ms(
    log_group_name: str, region: str
) -> tuple[str | None, int | None]:
    response = _aws_json(
        [
            "logs",
            "describe-log-streams",
            "--log-group-name",
            log_group_name,
            "--order-by",
            "LastEventTime",
            "--descending",
            "--max-items",
            "1",
        ],
        region,
    )
    streams = response.get("logStreams", [])
    if not streams:
        return None, None
    stream = streams[0]
    return stream.get("logStreamName"), stream.get("lastEventTimestamp")


def _check_cloudwatch_freshness(stack_name: str, region: str) -> list[CheckResult]:
    freshness_seconds = int(os.environ.get("CLOUDWATCH_LOG_FRESHNESS_SECONDS", "86400"))
    cutoff_ms = int((time.time() - freshness_seconds) * 1000)
    suffixes = _csv_env("CLOUDWATCH_FRESH_LOG_GROUPS", DEFAULT_FRESH_LOG_GROUP_SUFFIXES)
    results: list[CheckResult] = []

    for suffix in suffixes:
        group_name = f"/ecs/{stack_name}/{suffix}"
        try:
            stream_name, latest_ms = _latest_cloudwatch_event_ms(group_name, region)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            results.append(
                CheckResult(False, f"{group_name} freshness check failed: {exc}")
            )
            continue

        results.append(
            CheckResult(
                latest_ms is not None and latest_ms >= cutoff_ms,
                f"{group_name} latest stream={stream_name!r} last_event_ms={latest_ms!r}",
            )
        )

    return results


def _check_loki_delivery(stack_name: str) -> list[CheckResult]:
    loki_url = os.environ.get("LOKI_URL")
    if not loki_url:
        return [CheckResult(True, "Loki delivery skipped; LOKI_URL is not set")]

    loki_url = _normalized_loki_url(loki_url)
    results = [*_check_loki_log_group_inventory(stack_name, loki_url)]
    freshness_seconds = int(
        os.environ.get(
            "LOKI_FRESHNESS_SECONDS",
            os.environ.get("CLOUDWATCH_LOG_FRESHNESS_SECONDS", "86400"),
        )
    )
    start_ns = int((time.time() - freshness_seconds) * 1_000_000_000)
    log_group_suffixes = _csv_env(
        "LOKI_FRESH_LOG_GROUPS", DEFAULT_FRESH_LOKI_LOG_GROUP_SUFFIXES
    )

    for suffix in log_group_suffixes:
        log_group = f"/ecs/{stack_name}/{suffix}"
        query = f'{{stack="{stack_name}",environment="aws",log_group="{log_group}"}}'
        try:
            response = httpx.get(
                f"{loki_url.rstrip('/')}/loki/api/v1/query_range",
                params={"query": query, "start": str(start_ns), "limit": "1"},
                timeout=10,
            )
            payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            results.append(
                CheckResult(False, f"Loki query failed for {log_group}: {exc}")
            )
            continue

        streams = payload.get("data", {}).get("result", [])
        results.append(
            CheckResult(
                response.status_code == 200 and len(streams) > 0,
                f"Loki log_group={log_group!r} status={response.status_code} streams={len(streams)}",
            )
        )

    return results


def _normalized_loki_url(loki_url: str) -> str:
    parsed = urlparse(loki_url)
    if parsed.hostname != "localhost":
        return loki_url

    netloc = "127.0.0.1"
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


def _check_loki_log_group_inventory(
    stack_name: str, loki_url: str
) -> list[CheckResult]:
    lookback_seconds = int(os.environ.get("LOKI_LABEL_LOOKBACK_SECONDS", "2592000"))
    start_ns = int((time.time() - lookback_seconds) * 1_000_000_000)
    expected = set(_expected_loki_log_group_names(stack_name))

    try:
        response = httpx.get(
            f"{loki_url.rstrip('/')}/loki/api/v1/series",
            params={
                "match[]": f'{{stack="{stack_name}",environment="aws"}}',
                "start": str(start_ns),
            },
            timeout=10,
        )
        payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        return [CheckResult(False, f"Loki log group inventory failed: {exc}")]

    series = payload.get("data", [])
    actual = {
        stream["log_group"]
        for stream in series
        if isinstance(stream, dict) and isinstance(stream.get("log_group"), str)
    }
    old_schema_services = sorted(
        {
            stream["service"]
            for stream in series
            if isinstance(stream, dict)
            and isinstance(stream.get("service"), str)
            and "log_group" not in stream
        }
    )
    missing = sorted(expected - actual)
    observed = sorted(actual)

    return [
        CheckResult(
            response.status_code == 200,
            f"Loki series inventory status={response.status_code}",
        ),
        CheckResult(
            bool(actual),
            f"Loki observed log_group labels: {', '.join(observed)}"
            if actual
            else "Loki has no observed log_group labels. Point LOKI_URL at a reachable local or hosted Loki endpoint after logs have been shipped there.",
        ),
        CheckResult(
            True,
            "Loki log_group labels not observed yet for quiet groups: "
            f"{', '.join(missing)}"
            if missing
            else "Loki observed every expected log_group label",
        ),
        CheckResult(
            bool(actual) or not old_schema_services,
            "Loki has historical old-schema streams without log_group labels for services: "
            f"{', '.join(old_schema_services)}"
            if old_schema_services
            else "Loki has no old-schema streams without log_group labels",
        ),
    ]


def main() -> int:
    region = os.environ.get("AWS_REGION", "eu-central-1")
    stack_name = os.environ.get("STACK_NAME", "aws-sdlc-containers")
    results = [
        *_check_cloudwatch_log_inventory(stack_name, region),
        *_check_cloudwatch_freshness(stack_name, region),
        *_check_loki_delivery(stack_name),
    ]

    for result in results:
        prefix = "OK" if result.ok else "FAIL"
        stream = sys.stdout if result.ok else sys.stderr
        print(f"{prefix}: {result.message}", file=stream)

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
