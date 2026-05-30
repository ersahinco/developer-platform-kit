#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


def _aws_json(args: list[str]) -> dict[str, Any]:
    region = os.getenv("AWS_REGION", "eu-central-1")
    completed = subprocess.run(
        ["aws", *args, "--region", region, "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(completed.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("AWS CLI returned non-object JSON")
    return data


def task_definition_label(task_definition_arn: str) -> str:
    return task_definition_arn.rsplit("/", 1)[-1]


def deployment_summary(deployment: dict[str, Any]) -> str:
    return " ".join(
        [
            str(deployment.get("status", "UNKNOWN")),
            task_definition_label(str(deployment.get("taskDefinition", ""))),
            f"rollout={deployment.get('rolloutState', 'UNKNOWN')}",
            f"desired={deployment.get('desiredCount', 0)}",
            f"running={deployment.get('runningCount', 0)}",
            f"pending={deployment.get('pendingCount', 0)}",
            f"failed={deployment.get('failedTasks', 0)}",
        ]
    )


def service_is_stable(service: dict[str, Any]) -> bool:
    deployments = service.get("deployments", [])
    primary = next(
        (
            deployment
            for deployment in deployments
            if deployment.get("status") == "PRIMARY"
        ),
        None,
    )
    if primary is None or primary.get("rolloutState") != "COMPLETED":
        return False
    desired = int(service.get("desiredCount", 0))
    running = int(service.get("runningCount", 0))
    pending = int(service.get("pendingCount", 0))
    return desired == running and pending == 0


def service_has_failed_rollout(service: dict[str, Any]) -> bool:
    return any(
        deployment.get("rolloutState") == "FAILED"
        for deployment in service.get("deployments", [])
    )


def service_event_key(event: dict[str, Any]) -> str:
    return f"{event.get('createdAt')}|{event.get('message')}"


def recent_events(service: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    events = service.get("events", [])
    if not isinstance(events, list):
        return []
    return [event for event in events[:limit] if isinstance(event, dict)]


def target_group_arns(service: dict[str, Any]) -> list[str]:
    load_balancers = service.get("loadBalancers", [])
    if not isinstance(load_balancers, list):
        return []
    arns: list[str] = []
    for load_balancer in load_balancers:
        if not isinstance(load_balancer, dict):
            continue
        arn = load_balancer.get("targetGroupArn")
        if isinstance(arn, str) and arn:
            arns.append(arn)
    return arns


def target_health_summary(target_health: dict[str, Any]) -> str:
    descriptions = target_health.get("TargetHealthDescriptions", [])
    states = Counter(
        item.get("TargetHealth", {}).get("State", "unknown")
        for item in descriptions
        if isinstance(item, dict)
    )
    if not states:
        return "targets=0"
    return ", ".join(f"{state}={count}" for state, count in sorted(states.items()))


def rollout_line(
    service: dict[str, Any],
    *,
    elapsed_seconds: int,
    target_health: list[str],
) -> str:
    deployments = service.get("deployments", [])
    deployment_text = " | ".join(
        deployment_summary(deployment)
        for deployment in deployments
        if isinstance(deployment, dict)
    )
    target_text = "; ".join(target_health) if target_health else "no-target-groups"
    return (
        f"[{elapsed_seconds:>4}s] desired={service.get('desiredCount', 0)} "
        f"running={service.get('runningCount', 0)} "
        f"pending={service.get('pendingCount', 0)} "
        f"deployments=[{deployment_text}] targets=[{target_text}]"
    )


def markdown_summary(
    *,
    cluster: str,
    service: str,
    task_definition: str | None,
    elapsed_seconds: int,
    stable: bool,
    service_document: dict[str, Any],
    target_health: list[str],
) -> str:
    service_state = service_document["services"][0]
    status = "completed" if stable else "failed"
    lines = [
        "### ECS rollout",
        "",
        f"- Status: {status}",
        f"- Cluster: `{cluster}`",
        f"- Service: `{service}`",
        f"- Elapsed: {elapsed_seconds}s",
    ]
    if task_definition:
        lines.append(
            f"- Target task definition: `{task_definition_label(task_definition)}`"
        )
    if target_health:
        lines.append(f"- Target health: {'; '.join(target_health)}")
    lines.extend(["", "Recent service events:"])
    for event in recent_events(service_state, limit=5):
        lines.append(f"- {event.get('createdAt')}: {event.get('message')}")
    return "\n".join(lines) + "\n"


def append_file(path: str | None, content: str) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(content)


def _describe_service(cluster: str, service: str) -> dict[str, Any]:
    return _aws_json(
        [
            "ecs",
            "describe-services",
            "--cluster",
            cluster,
            "--services",
            service,
        ]
    )


def _target_health_summaries(service: dict[str, Any]) -> list[str]:
    summaries: list[str] = []
    for arn in target_group_arns(service):
        try:
            document = _aws_json(
                ["elbv2", "describe-target-health", "--target-group-arn", arn]
            )
        except (subprocess.CalledProcessError, RuntimeError) as error:
            summaries.append(f"{arn.rsplit('/', 2)[-2]}=unavailable({error})")
            continue
        summaries.append(f"{arn.rsplit('/', 2)[-2]}:{target_health_summary(document)}")
    return summaries


def observe_rollout(
    *,
    cluster: str,
    service: str,
    task_definition: str | None,
    poll_seconds: int,
    timeout_seconds: int,
    summary_file: str | None,
    output_file: str | None,
) -> int:
    started = time.monotonic()
    seen_events: set[str] = set()
    last_line = ""
    last_document: dict[str, Any] | None = None
    last_target_health: list[str] = []

    print(f"Observing ECS rollout for {cluster}/{service}", flush=True)
    if task_definition:
        print(
            f"Target task definition: {task_definition_label(task_definition)}",
            flush=True,
        )

    while True:
        elapsed = int(time.monotonic() - started)
        document = _describe_service(cluster, service)
        services = document.get("services", [])
        if not services:
            raise RuntimeError(f"ECS service {service!r} was not found in {cluster!r}")
        service_state = services[0]
        last_document = document
        last_target_health = _target_health_summaries(service_state)
        line = rollout_line(
            service_state,
            elapsed_seconds=elapsed,
            target_health=last_target_health,
        )
        if line != last_line:
            print(line, flush=True)
            last_line = line

        for event in reversed(recent_events(service_state, limit=10)):
            key = service_event_key(event)
            if key in seen_events:
                continue
            seen_events.add(key)
            print(
                f"event {event.get('createdAt')}: {event.get('message')}",
                flush=True,
            )

        if service_is_stable(service_state):
            elapsed = int(time.monotonic() - started)
            print(f"ECS rollout completed in {elapsed}s", flush=True)
            append_file(output_file, f"rollout_seconds={elapsed}\n")
            append_file(
                summary_file,
                markdown_summary(
                    cluster=cluster,
                    service=service,
                    task_definition=task_definition,
                    elapsed_seconds=elapsed,
                    stable=True,
                    service_document=document,
                    target_health=last_target_health,
                ),
            )
            return 0

        if service_has_failed_rollout(service_state):
            print("ECS rollout entered FAILED state", file=sys.stderr, flush=True)
            break

        if elapsed >= timeout_seconds:
            print(
                f"ECS rollout did not stabilize within {timeout_seconds}s",
                file=sys.stderr,
                flush=True,
            )
            break

        time.sleep(poll_seconds)

    elapsed = int(time.monotonic() - started)
    if last_document is not None:
        append_file(
            summary_file,
            markdown_summary(
                cluster=cluster,
                service=service,
                task_definition=task_definition,
                elapsed_seconds=elapsed,
                stable=False,
                service_document=last_document,
                target_health=last_target_health,
            ),
        )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Observe an ECS service rollout.")
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--task-definition")
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--summary-file", default=os.getenv("GITHUB_STEP_SUMMARY"))
    parser.add_argument("--output-file", default=os.getenv("GITHUB_OUTPUT"))
    args = parser.parse_args(argv)

    if args.poll_seconds < 1:
        parser.error("--poll-seconds must be at least 1")
    if args.timeout_seconds < args.poll_seconds:
        parser.error(
            "--timeout-seconds must be greater than or equal to --poll-seconds"
        )

    try:
        return observe_rollout(
            cluster=args.cluster,
            service=args.service,
            task_definition=args.task_definition,
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.timeout_seconds,
            summary_file=args.summary_file,
            output_file=args.output_file,
        )
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.strip() or error.stdout.strip() or str(error)
        print(f"AWS CLI call failed while observing rollout: {stderr}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
