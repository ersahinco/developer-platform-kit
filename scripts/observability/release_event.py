#!/usr/bin/env python3
"""Emit portable release and rollback evidence events.

The event is useful as a GitHub artifact by default. If a reachable Loki push
endpoint is provided, the same JSON is also sent to the portable Grafana stack.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
import re
import sys
import subprocess
import time
from typing import Any
from urllib import error, request

DEFAULT_ALARM_SUFFIXES = [
    "app-target-5xx",
    "app-target-latency",
    "app-log-errors",
    "app-log-rollback-drill-faults",
    "order-event-consumer-failures",
    "data-export-job-failures",
]

REQUIRED_EVENT_FIELDS = [
    ("schema_version",),
    ("event_type",),
    ("status",),
    ("summary",),
    ("timestamp",),
    ("runtime_id",),
    ("workload_id",),
    ("deployment_id",),
    ("image_digest",),
    ("rollback_category",),
    ("source_workflow",),
    ("evidence_links",),
    ("alarm_snapshot",),
]


def _clean_optional(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return value


def _int_optional(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _github_context(env: dict[str, str]) -> dict[str, str | None]:
    server_url = env.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repository = env.get("GITHUB_REPOSITORY")
    run_id = env.get("GITHUB_RUN_ID")
    run_url = (
        f"{server_url}/{repository}/actions/runs/{run_id}"
        if repository and run_id
        else None
    )
    return {
        "repository": repository,
        "run_id": run_id,
        "run_attempt": env.get("GITHUB_RUN_ATTEMPT"),
        "run_url": run_url,
        "workflow": env.get("GITHUB_WORKFLOW"),
        "job": env.get("GITHUB_JOB"),
        "sha": env.get("GITHUB_SHA"),
        "ref_name": env.get("GITHUB_REF_NAME"),
        "actor": env.get("GITHUB_ACTOR"),
    }


def _default_alarm_names(stack_name: str) -> list[str]:
    return [f"{stack_name}-{suffix}" for suffix in DEFAULT_ALARM_SUFFIXES]


def _aws_json(args: list[str], region: str) -> dict[str, Any]:
    command = [
        "aws",
        *args,
        "--region",
        region,
        "--output",
        "json",
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout or "{}")


def capture_alarm_snapshot(
    *,
    stack_name: str,
    region: str,
    alarm_names: list[str] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC) if now is None else now
    names = alarm_names if alarm_names else _default_alarm_names(stack_name)
    snapshot: dict[str, Any] = {
        "captured_at": now.isoformat(),
        "region": region,
        "alarms": [],
        "errors": [],
    }
    if not names:
        return snapshot

    try:
        response = _aws_json(
            ["cloudwatch", "describe-alarms", "--alarm-names", *names],
            region,
        )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        snapshot["errors"].append(str(exc))
        return snapshot

    for alarm in response.get("MetricAlarms", []):
        snapshot["alarms"].append(
            {
                "name": alarm.get("AlarmName"),
                "state": alarm.get("StateValue"),
                "reason": alarm.get("StateReason"),
                "updated_at": alarm.get("StateUpdatedTimestamp"),
            }
        )
    return snapshot


def build_event(
    *,
    event_type: str,
    status: str,
    summary: str | None,
    service_name: str,
    image_tag: str | None,
    task_definition: str | None,
    previous_task_definition: str | None,
    drill_task_definition: str | None,
    plan_run_id: str | None,
    fault_mode: str | None,
    read_mode: str | None,
    write_mode: str | None,
    rollback_seconds: int | None,
    rollback_slo_seconds: int | None,
    verify_seconds: int | None,
    verify_slo_seconds: int | None,
    runtime_id: str | None = None,
    workload_id: str | None = None,
    deployment_id: str | None = None,
    image_digest: str | None = None,
    rollback_category: str | None = None,
    source_workflow: str | None = None,
    evidence_links: list[str] | None = None,
    alarm_snapshot: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if env is None else env)
    now = datetime.now(UTC) if now is None else now
    stack_name = env.get("STACK_NAME", "aws-sdlc-containers")
    environment = env.get("DEPLOYMENT_ENVIRONMENT", "aws")
    github = _github_context(env)
    resolved_runtime_id = runtime_id or env.get("RUNTIME_ID", "aws-ecs")
    resolved_workload_id = workload_id or service_name
    resolved_source_workflow = source_workflow or github.get("workflow")
    resolved_deployment_id = (
        deployment_id
        or task_definition
        or plan_run_id
        or github.get("run_id")
        or image_tag
    )
    resolved_evidence_links = list(evidence_links or [])
    github_run_url = github.get("run_url")
    if github_run_url and github_run_url not in resolved_evidence_links:
        resolved_evidence_links.append(github_run_url)

    return {
        "schema_version": "1",
        "event_type": event_type,
        "status": status,
        "summary": summary,
        "timestamp": now.isoformat(),
        "runtime_id": resolved_runtime_id,
        "workload_id": resolved_workload_id,
        "deployment_id": resolved_deployment_id,
        "image_digest": image_digest or env.get("IMAGE_DIGEST"),
        "rollback_category": rollback_category,
        "source_workflow": resolved_source_workflow,
        "evidence_links": resolved_evidence_links,
        "stack": {
            "name": stack_name,
            "environment": environment,
            "region": env.get("AWS_REGION", "eu-central-1"),
            "root_domain": env.get("ROOT_DOMAIN"),
        },
        "service": service_name,
        "revision": {
            "image_tag": image_tag,
            "task_definition": task_definition,
            "previous_task_definition": previous_task_definition,
            "drill_task_definition": drill_task_definition,
            "plan_run_id": plan_run_id,
        },
        "runtime": {
            "fault_mode": fault_mode,
            "read_mode": read_mode,
            "write_mode": write_mode,
        },
        "slo": {
            "rollback_seconds": rollback_seconds,
            "rollback_slo_seconds": rollback_slo_seconds,
            "verify_seconds": verify_seconds,
            "verify_slo_seconds": verify_slo_seconds,
        },
        "alarm_snapshot": alarm_snapshot
        if alarm_snapshot is not None
        else {
            "captured_at": None,
            "region": env.get("AWS_REGION", "eu-central-1"),
            "alarms": [],
            "errors": [],
        },
        "github": github,
        "correlation": {
            "stack": stack_name,
            "environment": environment,
            "service": service_name,
            "runtime_id": resolved_runtime_id,
            "workload_id": resolved_workload_id,
            "deployment_id": resolved_deployment_id,
            "image_digest": image_digest or env.get("IMAGE_DIGEST"),
            "image_tag": image_tag,
            "task_definition": task_definition,
            "github_run_id": env.get("GITHUB_RUN_ID"),
        },
    }


def validate_event_contract(event: dict[str, Any]) -> None:
    missing: list[str] = []
    for path in REQUIRED_EVENT_FIELDS:
        current: Any = event
        for part in path:
            if not isinstance(current, dict) or part not in current:
                missing.append(".".join(path))
                break
            current = current[part]

    if missing:
        raise ValueError(
            "Release event is missing required contract fields: "
            + ", ".join(sorted(missing))
        )


def render_markdown(event: dict[str, Any]) -> str:
    revision = event["revision"]
    slo = event["slo"]
    github = event["github"]
    alarm_snapshot = event.get("alarm_snapshot", {})
    lines = [
        "# Release Evidence Event",
        "",
        f"- Type: {event['event_type']}",
        f"- Status: {event['status']}",
        f"- Time: {event['timestamp']}",
        f"- Runtime: {event['runtime_id']}",
        f"- Workload: {event['workload_id']}",
        f"- Deployment: `{event['deployment_id']}`",
        f"- Stack: {event['stack']['name']} ({event['stack']['environment']})",
        f"- Service: {event['service']}",
    ]
    if event.get("image_digest"):
        lines.append(f"- Image digest: `{event['image_digest']}`")
    if event.get("source_workflow"):
        lines.append(f"- Source workflow: {event['source_workflow']}")
    if event.get("summary"):
        lines.append(f"- Summary: {event['summary']}")
    if github.get("run_url"):
        lines.append(f"- GitHub run: {github['run_url']}")
    if revision.get("image_tag"):
        lines.append(f"- Image tag: `{revision['image_tag']}`")
    if revision.get("task_definition"):
        lines.append(f"- Task definition: `{revision['task_definition']}`")
    if revision.get("previous_task_definition"):
        lines.append(
            f"- Previous task definition: `{revision['previous_task_definition']}`"
        )
    if revision.get("drill_task_definition"):
        lines.append(f"- Drill task definition: `{revision['drill_task_definition']}`")
    if revision.get("plan_run_id"):
        lines.append(f"- Plan run: `{revision['plan_run_id']}`")

    rollback_line = None
    if slo.get("rollback_seconds") is not None:
        rollback_line = f"- Rollback: {slo['rollback_seconds']}s"
        if slo.get("rollback_slo_seconds") is not None:
            rollback_line += f" / {slo['rollback_slo_seconds']}s"
    verify_line = None
    if slo.get("verify_seconds") is not None:
        verify_line = f"- Verification: {slo['verify_seconds']}s"
        if slo.get("verify_slo_seconds") is not None:
            verify_line += f" / {slo['verify_slo_seconds']}s"
    slo_lines = [rollback_line, verify_line]
    present_slo_lines = [line for line in slo_lines if line is not None]
    if present_slo_lines:
        lines.extend(["", "## SLO Evidence", *present_slo_lines])

    alarm_lines = []
    for alarm in alarm_snapshot.get("alarms", []):
        alarm_lines.append(
            "- %s: %s"
            % (
                alarm.get("name", "unknown"),
                alarm.get("state", "unknown"),
            )
        )
    for alarm_error in alarm_snapshot.get("errors", []):
        alarm_lines.append(f"- Alarm snapshot error: {alarm_error}")
    if alarm_lines:
        lines.extend(["", "## Alarm Snapshot", *alarm_lines])

    lines.extend(
        [
            "",
            "## Loki Query",
            "",
            (
                '`{stack="%s",environment="%s",service="%s",event_type="%s"}`'
                % (
                    event["stack"]["name"],
                    event["stack"]["environment"],
                    event["service"],
                    event["event_type"],
                )
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def write_event(event: dict[str, Any], output_dir: Path) -> tuple[Path, Path, Path]:
    validate_event_contract(event)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "release-event.json"
    jsonl_path = output_dir / "release-event.jsonl"
    markdown_path = output_dir / "release-event.md"
    line = json.dumps(event, sort_keys=True)
    json_path.write_text(
        json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    jsonl_path.write_text(line + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(event), encoding="utf-8")
    return json_path, jsonl_path, markdown_path


def _label_value(value: str | None) -> str:
    if value is None:
        return "unknown"
    return re.sub(r"[^a-zA-Z0-9_.:-]", "_", value)[:120] or "unknown"


def loki_push_url(env: dict[str, str], explicit_url: str | None) -> str | None:
    if explicit_url:
        return explicit_url
    if env.get("LOKI_PUSH_URL"):
        return env["LOKI_PUSH_URL"]
    loki_url = env.get("LOKI_URL")
    if not loki_url:
        return None
    return loki_url.rstrip("/") + "/loki/api/v1/push"


def push_loki(event: dict[str, Any], url: str) -> None:
    labels = {
        "stack": _label_value(event["stack"]["name"]),
        "environment": _label_value(event["stack"]["environment"]),
        "service": _label_value(event["service"]),
        "event_type": _label_value(event["event_type"]),
        "status": _label_value(event["status"]),
        "github_run_id": _label_value(event["github"].get("run_id")),
        "workflow": _label_value(event["github"].get("workflow")),
    }
    payload = {
        "streams": [
            {
                "stream": labels,
                "values": [
                    [str(time.time_ns()), json.dumps(event, sort_keys=True)],
                ],
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        if response.status >= 300:
            raise RuntimeError(f"Loki push failed with HTTP {response.status}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit a portable release evidence event."
    )
    parser.add_argument("--event-type", required=True)
    parser.add_argument(
        "--status", default=os.environ.get("RELEASE_EVENT_STATUS", "unknown")
    )
    parser.add_argument("--summary")
    parser.add_argument("--service-name", default="app")
    parser.add_argument("--image-tag")
    parser.add_argument("--task-definition")
    parser.add_argument("--previous-task-definition")
    parser.add_argument("--drill-task-definition")
    parser.add_argument("--plan-run-id")
    parser.add_argument("--fault-mode")
    parser.add_argument("--read-mode")
    parser.add_argument("--write-mode")
    parser.add_argument("--rollback-seconds")
    parser.add_argument("--rollback-slo-seconds")
    parser.add_argument("--verify-seconds")
    parser.add_argument("--verify-slo-seconds")
    parser.add_argument("--runtime-id")
    parser.add_argument("--workload-id")
    parser.add_argument("--deployment-id")
    parser.add_argument("--image-digest")
    parser.add_argument("--rollback-category")
    parser.add_argument("--source-workflow")
    parser.add_argument("--evidence-link", action="append", default=[])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/aws-sdlc-containers-release-event"),
    )
    parser.add_argument("--push-loki", action="store_true")
    parser.add_argument("--loki-url")
    parser.add_argument(
        "--loki-push-best-effort",
        action="store_true",
        help="Keep the artifact even when an optional Loki push fails.",
    )
    parser.add_argument(
        "--include-alarms",
        action="store_true",
        help="Include a CloudWatch alarm-state snapshot for rollback context.",
    )
    parser.add_argument(
        "--alarm-name",
        action="append",
        default=[],
        help="CloudWatch alarm name to capture; defaults to the app alarm set.",
    )
    parser.add_argument(
        "--strict-alarms",
        action="store_true",
        help="Fail if alarm snapshot collection fails.",
    )
    args = parser.parse_args()

    env = dict(os.environ)
    alarm_snapshot = None
    if args.include_alarms:
        alarm_snapshot = capture_alarm_snapshot(
            stack_name=env.get("STACK_NAME", "aws-sdlc-containers"),
            region=env.get("AWS_REGION", "eu-central-1"),
            alarm_names=args.alarm_name,
        )
        if args.strict_alarms and alarm_snapshot["errors"]:
            for alarm_error in alarm_snapshot["errors"]:
                print(f"Alarm snapshot failed: {alarm_error}", file=sys.stderr)
            return 1

    event = build_event(
        event_type=args.event_type,
        status=args.status,
        summary=_clean_optional(args.summary),
        service_name=args.service_name,
        image_tag=_clean_optional(args.image_tag),
        task_definition=_clean_optional(args.task_definition),
        previous_task_definition=_clean_optional(args.previous_task_definition),
        drill_task_definition=_clean_optional(args.drill_task_definition),
        plan_run_id=_clean_optional(args.plan_run_id),
        fault_mode=_clean_optional(args.fault_mode),
        read_mode=_clean_optional(args.read_mode),
        write_mode=_clean_optional(args.write_mode),
        rollback_seconds=_int_optional(args.rollback_seconds),
        rollback_slo_seconds=_int_optional(args.rollback_slo_seconds),
        verify_seconds=_int_optional(args.verify_seconds),
        verify_slo_seconds=_int_optional(args.verify_slo_seconds),
        runtime_id=_clean_optional(args.runtime_id),
        workload_id=_clean_optional(args.workload_id),
        deployment_id=_clean_optional(args.deployment_id),
        image_digest=_clean_optional(args.image_digest),
        rollback_category=_clean_optional(args.rollback_category),
        source_workflow=_clean_optional(args.source_workflow),
        evidence_links=args.evidence_link,
        alarm_snapshot=alarm_snapshot,
        env=env,
    )
    json_path, jsonl_path, markdown_path = write_event(event, args.output_dir)
    print(f"Wrote {markdown_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {jsonl_path}")

    if args.push_loki:
        url = loki_push_url(env, args.loki_url)
        if url is None:
            print("LOKI_PUSH_URL or LOKI_URL not set; skipping Loki push.")
        else:
            try:
                push_loki(event, url)
                print(f"Pushed release event to {url}")
            except (OSError, RuntimeError, error.URLError) as exc:
                print(f"Failed to push release event to Loki: {exc}", file=sys.stderr)
                if not args.loki_push_best_effort:
                    return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
