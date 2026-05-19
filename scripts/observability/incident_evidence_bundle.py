"""
incident_evidence_bundle.py - Build portable incident context bundles.

The bundle is intentionally evidence, not diagnosis. It collects bounded AWS
state and emits query hints for Grafana tools so a human operator can
correlate logs, metrics, traces, deploys, and rollback state without depending
on a cloud-only observability feature.

Usage:
    python scripts/observability/incident_evidence_bundle.py --output-dir /tmp/incident

Environment:
    AWS_REGION          Default: eu-central-1
    STACK_NAME          Default: aws-sdlc-containers
    LOKI_URL            Optional Loki base URL for release-event lookup
    RELEASE_EVENTS_DIR  Optional directory containing release-event artifacts
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import parse, request

from scripts.observability.platform_inventory import dapr_workload_service_name
from scripts.observability.platform_inventory import incident_alarm_names

CORRELATION_FIELDS = [
    "stack",
    "environment",
    "service",
    "container",
    "request_id",
    "trace_id",
    "task_definition",
    "image_tag",
    "github_run_id",
    "order_id",
    "event_id",
    "export_run_id",
]


def _aws_json(args: list[str], region: str) -> dict[str, Any]:
    command = ["aws", *args, "--region", region, "--output", "json"]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _safe_aws_json(args: list[str], region: str) -> dict[str, Any]:
    try:
        return _aws_json(args, region)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return {"error": str(exc), "args": args}


def _primary_deployment(service: dict[str, Any]) -> dict[str, Any]:
    deployments = service.get("deployments", [])
    if not isinstance(deployments, list):
        return {}
    for deployment in deployments:
        if isinstance(deployment, dict) and deployment.get("status") == "PRIMARY":
            return deployment
    return {}


def _container_images(task_definition: dict[str, Any]) -> list[dict[str, str]]:
    containers = task_definition.get("containerDefinitions", [])
    if not isinstance(containers, list):
        return []
    images = []
    for container in containers:
        if not isinstance(container, dict):
            continue
        name = container.get("name")
        image = container.get("image")
        if isinstance(name, str) and isinstance(image, str):
            images.append(
                {"name": name, "image": image, "image_tag": image.rsplit(":", 1)[-1]}
            )
    return images


def _github_context() -> dict[str, str | None]:
    keys = [
        "GITHUB_REPOSITORY",
        "GITHUB_RUN_ID",
        "GITHUB_SHA",
        "GITHUB_REF_NAME",
        "GITHUB_WORKFLOW",
    ]
    return {key.lower(): os.environ.get(key) for key in keys}


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _release_event_summary(
    event: dict[str, Any],
    *,
    source: str | None = None,
) -> dict[str, Any]:
    github = event.get("github", {})
    revision = event.get("revision", {})
    runtime = event.get("runtime", {})
    slo = event.get("slo", {})
    if not isinstance(github, dict):
        github = {}
    if not isinstance(revision, dict):
        revision = {}
    if not isinstance(runtime, dict):
        runtime = {}
    if not isinstance(slo, dict):
        slo = {}

    summary = {
        "event_type": event.get("event_type"),
        "status": event.get("status"),
        "summary": event.get("summary"),
        "timestamp": event.get("timestamp"),
        "service": event.get("service"),
        "github_run_id": github.get("run_id"),
        "github_run_url": github.get("run_url"),
        "workflow": github.get("workflow"),
        "image_tag": revision.get("image_tag"),
        "task_definition": revision.get("task_definition"),
        "previous_task_definition": revision.get("previous_task_definition"),
        "drill_task_definition": revision.get("drill_task_definition"),
        "plan_run_id": revision.get("plan_run_id"),
        "fault_mode": runtime.get("fault_mode"),
        "read_mode": runtime.get("read_mode"),
        "write_mode": runtime.get("write_mode"),
        "rollback_seconds": slo.get("rollback_seconds"),
        "verify_seconds": slo.get("verify_seconds"),
    }
    if source:
        summary["source"] = source
    return summary


def _event_identity(event: dict[str, Any]) -> tuple[object, object, object]:
    github = event.get("github", {})
    if not isinstance(github, dict):
        github = {}
    return (event.get("timestamp"), event.get("event_type"), github.get("run_id"))


def _read_release_event_file(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    events: list[dict[str, Any]] = []
    if path.suffix == ".jsonl":
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
        return events

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(value, dict):
        events.append(value)
    elif isinstance(value, list):
        events.extend(item for item in value if isinstance(item, dict))
    return events


def _load_release_events(
    release_events_dir: Path | None,
    *,
    window_start: datetime,
    window_end: datetime,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if release_events_dir is None or not release_events_dir.exists():
        return []

    candidates = [
        *release_events_dir.rglob("release-event.json"),
        *release_events_dir.rglob("release-event.jsonl"),
    ]
    seen: set[tuple[object, object, object]] = set()
    events: list[dict[str, Any]] = []
    for path in sorted(candidates):
        for event in _read_release_event_file(path):
            timestamp = _parse_datetime(event.get("timestamp"))
            if timestamp is None:
                continue
            if timestamp < window_start or timestamp > window_end:
                continue
            identity = _event_identity(event)
            if identity in seen:
                continue
            seen.add(identity)
            events.append(_release_event_summary(event, source="artifact"))

    events.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return events[:limit]


def _summary_identity(event: dict[str, Any]) -> tuple[object, object, object]:
    return (event.get("timestamp"), event.get("event_type"), event.get("github_run_id"))


def _merge_release_events(
    events: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    seen: set[tuple[object, object, object]] = set()
    merged: list[dict[str, Any]] = []
    for event in sorted(
        events,
        key=lambda item: str(item.get("timestamp") or ""),
        reverse=True,
    ):
        identity = _summary_identity(event)
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(event)
        if len(merged) >= limit:
            break
    return merged


def _loki_json(loki_url: str, params: dict[str, str]) -> dict[str, Any]:
    query_string = parse.urlencode(params)
    url = f"{loki_url.rstrip('/')}/loki/api/v1/query_range?{query_string}"
    req = request.Request(url, method="GET")
    with request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_loki_release_events(
    loki_url: str | None,
    *,
    stack_name: str,
    window_start: datetime,
    window_end: datetime,
    limit: int = 10,
) -> tuple[list[dict[str, Any]], str | None]:
    if not loki_url:
        return [], None

    query = (
        f'{{stack="{stack_name}",environment="aws",'
        'event_type=~"app_deploy|app_rollback_drill|'
        'data_runtime_rollback_drill|infra_apply"}}'
    )
    try:
        response = _loki_json(
            loki_url,
            {
                "query": query,
                "start": str(int(window_start.timestamp() * 1_000_000_000)),
                "end": str(int(window_end.timestamp() * 1_000_000_000)),
                "limit": str(limit),
                "direction": "BACKWARD",
            },
        )
    except (OSError, json.JSONDecodeError) as exc:
        return [], str(exc)

    data = response.get("data", {})
    results = data.get("result", []) if isinstance(data, dict) else []
    if not isinstance(results, list):
        return [], "Loki response data.result was not a list"

    events: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        values = result.get("values", [])
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, list) or len(value) < 2:
                continue
            line = value[1]
            if not isinstance(line, str):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            timestamp = _parse_datetime(event.get("timestamp"))
            if timestamp is None or timestamp < window_start or timestamp > window_end:
                continue
            events.append(_release_event_summary(event, source="loki"))

    return _merge_release_events(events, limit=limit), None


def _query_hints(
    stack_name: str, service_name: str, root_domain: str
) -> dict[str, Any]:
    base_labels = f'stack="{stack_name}",environment="aws",service="{service_name}"'
    relay_service_name = dapr_workload_service_name()
    return {
        "grafana_dashboards": [
            "AWS SDLC Containers / App Overview",
            "AWS SDLC Containers / Log Groups",
        ],
        "loki": [
            {
                "name": "service logs by request id",
                "expr": f'{{{base_labels}}} |= "<request_id>"',
            },
            {
                "name": "app errors",
                "expr": f'{{{base_labels}}} |~ "(?i)(error|exception|traceback)"',
            },
            {
                "name": "order event relay",
                "expr": f'{{stack="{stack_name}",environment="aws",service="{relay_service_name}"}} |= "<event_id>"',
            },
            {
                "name": "delivery events",
                "expr": f'{{stack="{stack_name}",environment="aws",event_type=~"app_deploy|app_rollback_drill|data_runtime_rollback_drill|infra_apply"}}',
            },
        ],
        "prometheus": [
            {
                "name": "5xx rate",
                "expr": 'sum by (route) (rate(http_requests_total{status=~"5.."}[5m]))',
            },
            {
                "name": "p95 latency",
                "expr": "histogram_quantile(0.95, sum by (le, route) (rate(http_request_duration_seconds_bucket[5m])))",
            },
            {
                "name": "readiness failures",
                "expr": 'sum(rate(http_requests_total{route="/ready",status=~"5.."}[5m]))',
            },
        ],
        "tempo": [
            {
                "service": "aws-sdlc-containers-api",
                "tags": ["request_id", "http.route", "http.status_code"],
            }
        ],
        "operator_commands": [
            "make observability",
            f"BASE_URL=https://api.{root_domain} make observability-cloud-traffic",
            "make observability-delivery-verify",
        ],
    }


def build_bundle(
    *,
    stack_name: str,
    service_name: str,
    region: str,
    root_domain: str,
    lookback_minutes: int,
    release_events_dir: Path | None = None,
    loki_url: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=lookback_minutes)
    service_response = _safe_aws_json(
        [
            "ecs",
            "describe-services",
            "--cluster",
            stack_name,
            "--services",
            service_name,
        ],
        region,
    )
    service = {}
    services = service_response.get("services", [])
    if isinstance(services, list) and services:
        first = services[0]
        if isinstance(first, dict):
            service = first

    primary = _primary_deployment(service)
    task_definition_arn = primary.get("taskDefinition") or service.get("taskDefinition")
    task_definition_response: dict[str, Any] = {}
    task_definition: dict[str, Any] = {}
    if isinstance(task_definition_arn, str) and task_definition_arn:
        task_definition_response = _safe_aws_json(
            [
                "ecs",
                "describe-task-definition",
                "--task-definition",
                task_definition_arn,
            ],
            region,
        )
        task_definition_value = task_definition_response.get("taskDefinition", {})
        if isinstance(task_definition_value, dict):
            task_definition = task_definition_value

    alarm_response = _safe_aws_json(
        [
            "cloudwatch",
            "describe-alarms",
            "--alarm-names",
            *incident_alarm_names(stack_name),
        ],
        region,
    )
    metric_alarms = alarm_response.get("MetricAlarms", [])
    alarms = metric_alarms if isinstance(metric_alarms, list) else []
    artifact_release_events = _load_release_events(
        release_events_dir,
        window_start=window_start,
        window_end=now,
    )
    loki_release_events, loki_release_event_error = _load_loki_release_events(
        loki_url,
        stack_name=stack_name,
        window_start=window_start,
        window_end=now,
    )
    release_events = _merge_release_events(
        [*loki_release_events, *artifact_release_events],
        limit=10,
    )

    return {
        "schema_version": "1",
        "generated_at": now.isoformat(),
        "window": {
            "start": window_start.isoformat(),
            "end": now.isoformat(),
            "lookback_minutes": lookback_minutes,
        },
        "stack": {
            "name": stack_name,
            "region": region,
            "environment": "aws",
            "root_domain": root_domain,
        },
        "github": _github_context(),
        "ecs": {
            "cluster": stack_name,
            "service": service_name,
            "service_status": service.get("status"),
            "desired_count": service.get("desiredCount"),
            "running_count": service.get("runningCount"),
            "pending_count": service.get("pendingCount"),
            "primary_rollout_state": primary.get("rolloutState"),
            "task_definition": task_definition_arn,
            "containers": _container_images(task_definition),
            "raw_errors": [
                item.get("error")
                for item in [service_response, task_definition_response]
                if isinstance(item.get("error"), str)
            ],
        },
        "alarms": [
            {
                "name": alarm.get("AlarmName"),
                "state": alarm.get("StateValue"),
                "reason": alarm.get("StateReason"),
                "updated_at": alarm.get("StateUpdatedTimestamp"),
            }
            for alarm in alarms
            if isinstance(alarm, dict)
        ],
        "release_events": release_events,
        "release_event_sources": {
            "directory": str(release_events_dir) if release_events_dir else None,
            "artifact_count": len(artifact_release_events),
            "loki_url": loki_url,
            "loki_count": len(loki_release_events),
            "loki_error": loki_release_event_error,
            "loaded_count": len(release_events),
        },
        "correlation_fields": CORRELATION_FIELDS,
        "query_hints": _query_hints(stack_name, service_name, root_domain),
    }


def render_markdown(bundle: dict[str, Any]) -> str:
    ecs = bundle["ecs"]
    stack = bundle["stack"]
    lines = [
        "# Incident Evidence Bundle",
        "",
        f"- Generated: {bundle['generated_at']}",
        f"- Window: {bundle['window']['start']} to {bundle['window']['end']}",
        f"- Stack: {stack['name']} ({stack['region']})",
        f"- ECS service: {ecs['service']} rollout={ecs.get('primary_rollout_state')}",
        f"- Task definition: {ecs.get('task_definition')}",
        "",
        "## Containers",
    ]
    for container in ecs.get("containers", []):
        lines.append(f"- {container['name']}: `{container['image']}`")

    lines.extend(["", "## Alarm States"])
    alarms = bundle.get("alarms", [])
    if alarms:
        for alarm in alarms:
            lines.append(f"- {alarm['name']}: {alarm['state']} - {alarm.get('reason')}")
    else:
        lines.append("- No alarm states collected.")

    lines.extend(["", "## Recent Delivery Events"])
    release_events = bundle.get("release_events", [])
    if release_events:
        for event in release_events:
            detail = event.get("summary") or event.get("event_type")
            run = event.get("github_run_id") or "unknown run"
            status = event.get("status") or "unknown"
            timestamp = event.get("timestamp") or "unknown time"
            source = event.get("source") or "unknown source"
            lines.append(f"- {timestamp}: {detail} ({status}, run {run}, {source})")
            if event.get("image_tag"):
                lines.append(f"  - image_tag: `{event['image_tag']}`")
            if event.get("task_definition"):
                lines.append(f"  - task_definition: `{event['task_definition']}`")
            if event.get("plan_run_id"):
                lines.append(f"  - plan_run_id: `{event['plan_run_id']}`")
    else:
        lines.append(
            "- No release events loaded from Loki or local artifacts. Download `release-evidence-*` artifacts or query the Grafana Delivery Events panel."
        )
    release_event_sources = bundle.get("release_event_sources", {})
    if release_event_sources.get("loki_error"):
        lines.append(
            f"- Loki release-event query error: {release_event_sources['loki_error']}"
        )

    lines.extend(["", "## Correlation Fields"])
    lines.append(", ".join(f"`{field}`" for field in bundle["correlation_fields"]))

    lines.extend(["", "## Grafana Dashboards"])
    for dashboard in bundle["query_hints"]["grafana_dashboards"]:
        lines.append(f"- {dashboard}")

    lines.extend(["", "## Query Hints", "", "### Loki"])
    for item in bundle["query_hints"]["loki"]:
        lines.append(f"- {item['name']}: `{item['expr']}`")
    lines.extend(["", "### Prometheus"])
    for item in bundle["query_hints"]["prometheus"]:
        lines.append(f"- {item['name']}: `{item['expr']}`")
    lines.extend(["", "### Tempo"])
    for item in bundle["query_hints"]["tempo"]:
        lines.append(f"- service `{item['service']}` tags: {', '.join(item['tags'])}")

    lines.extend(["", "## Operator Commands"])
    for command in bundle["query_hints"]["operator_commands"]:
        lines.append(f"- `{command}`")

    return "\n".join(lines) + "\n"


def write_bundle(bundle: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "incident-evidence.json"
    markdown_path = output_dir / "incident-evidence.md"
    json_path.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_markdown(bundle), encoding="utf-8")
    return json_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an incident evidence bundle.")
    parser.add_argument(
        "--stack-name", default=os.environ.get("STACK_NAME", "aws-sdlc-containers")
    )
    parser.add_argument("--service-name", default="app")
    parser.add_argument(
        "--region", default=os.environ.get("AWS_REGION", "eu-central-1")
    )
    parser.add_argument(
        "--root-domain", default=os.environ.get("ROOT_DOMAIN", "example.invalid")
    )
    parser.add_argument("--lookback-minutes", type=int, default=60)
    release_events_default = os.environ.get("RELEASE_EVENTS_DIR")
    parser.add_argument(
        "--release-events-dir",
        type=Path,
        default=Path(release_events_default) if release_events_default else None,
    )
    parser.add_argument("--loki-url", default=os.environ.get("LOKI_URL"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/aws-sdlc-containers-incident-evidence"),
    )
    args = parser.parse_args()

    bundle = build_bundle(
        stack_name=args.stack_name,
        service_name=args.service_name,
        region=args.region,
        root_domain=args.root_domain,
        lookback_minutes=args.lookback_minutes,
        release_events_dir=args.release_events_dir,
        loki_url=args.loki_url,
    )
    json_path, markdown_path = write_bundle(bundle, args.output_dir)
    print(f"Wrote {markdown_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
