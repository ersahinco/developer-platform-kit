"""
incident_evidence_bundle.py - Build portable incident context bundles.

The bundle is intentionally evidence, not diagnosis. It collects bounded AWS
state and emits query hints for Grafana-stack tools so a human operator, or a
future assistant-style workflow, can correlate logs, metrics, traces, deploys,
and rollback state without depending on a managed AI product.

Usage:
    python scripts/observability/incident_evidence_bundle.py --output-dir /tmp/incident

Environment:
    AWS_REGION  Default: eu-central-1
    STACK_NAME  Default: aws-sdlc-containers
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


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


def _alarm_names(stack_name: str) -> list[str]:
    return [
        f"{stack_name}-app-unhealthy-targets",
        f"{stack_name}-app-target-5xx",
        f"{stack_name}-app-target-latency",
        f"{stack_name}-rds-cpu-high",
        f"{stack_name}-rds-free-storage-low",
        f"{stack_name}-rds-connections-high",
        f"{stack_name}-order-events-dlq-visible",
        f"{stack_name}-data-export-scheduler-target-errors",
        f"{stack_name}-data-export-success-missing",
    ]


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


def _query_hints(
    stack_name: str, service_name: str, root_domain: str
) -> dict[str, Any]:
    base_labels = f'stack="{stack_name}",environment="aws",service="{service_name}"'
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
                "expr": f'{{stack="{stack_name}",environment="aws",service="order-event-consumer"}} |= "<event_id>"',
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
            "make grafana-tunnel",
            "make loki-tunnel",
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
        ["cloudwatch", "describe-alarms", "--alarm-names", *_alarm_names(stack_name)],
        region,
    )
    metric_alarms = alarm_response.get("MetricAlarms", [])
    alarms = metric_alarms if isinstance(metric_alarms, list) else []

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
        "correlation_fields": CORRELATION_FIELDS,
        "query_hints": _query_hints(stack_name, service_name, root_domain),
        "workflow_hints": {
            "rollback_drills": [
                ".github/workflows/app-rollback-drill.yml",
                ".github/workflows/data-runtime-rollback-drill.yml",
            ],
            "reviewed_infra": [
                ".github/workflows/infra-plan.yml",
                ".github/workflows/infra-apply.yml",
            ],
            "recent_runs": [
                "gh run list --workflow app-deploy.yml --limit 5",
                "gh run list --workflow app-rollback-drill.yml --limit 5",
                "gh run list --workflow data-runtime-rollback-drill.yml --limit 5",
                "gh run list --workflow infra-plan.yml --limit 5",
                "gh run list --workflow infra-apply.yml --limit 5",
            ],
        },
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
    for command in bundle["workflow_hints"]["recent_runs"]:
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
        "--root-domain", default=os.environ.get("ROOT_DOMAIN", "ersahinco-sandbox.eu")
    )
    parser.add_argument("--lookback-minutes", type=int, default=60)
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
    )
    json_path, markdown_path = write_bundle(bundle, args.output_dir)
    print(f"Wrote {markdown_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
