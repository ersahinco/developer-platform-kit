#!/usr/bin/env python3
"""Verify release-event push and query round-trip through Loki.

This is the activation check for CI-to-Loki delivery evidence. It pushes a
bounded probe event through the same release_event helper used by workflows,
then queries Loki until the probe is visible.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from scripts.observability import release_event


def loki_query_url(env: dict[str, str], explicit_url: str | None) -> str | None:
    if explicit_url:
        return explicit_url.rstrip("/")
    if env.get("LOKI_URL"):
        return env["LOKI_URL"].rstrip("/")
    push_url = env.get("LOKI_PUSH_URL", "")
    suffix = "/loki/api/v1/push"
    if push_url.endswith(suffix):
        return push_url[: -len(suffix)].rstrip("/")
    return None


def build_probe_event(env: dict[str, str], probe_id: str) -> dict[str, Any]:
    event = release_event.build_event(
        event_type="release_event_delivery_probe",
        status="success",
        summary="Release event Loki delivery probe",
        service_name="infra",
        image_tag=None,
        task_definition=None,
        plan_run_id=None,
        read_mode=None,
        write_mode=None,
        verify_seconds=None,
        verify_slo_seconds=None,
        env=env,
        now=datetime.now(UTC),
    )
    event["probe_id"] = probe_id
    event["correlation"]["probe_id"] = probe_id
    return event


def query_probe(
    *,
    loki_url: str,
    stack_name: str,
    environment: str,
    probe_id: str,
    timeout_seconds: int,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    query = (
        f'{{stack="{stack_name}",environment="{environment}",'
        'service="infra",event_type="release_event_delivery_probe"}'
        f' |= "{probe_id}"'
    )

    while time.monotonic() <= deadline:
        response = httpx.get(
            f"{loki_url.rstrip('/')}/loki/api/v1/query_range",
            params={
                "query": query,
                "start": str(int((time.time() - timeout_seconds) * 1_000_000_000)),
                "limit": "1",
                "direction": "BACKWARD",
            },
            timeout=10,
        )
        payload = response.json()
        streams = payload.get("data", {}).get("result", [])
        if response.status_code == 200 and streams:
            return True
        time.sleep(2)

    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify release-event push and query round-trip through Loki."
    )
    parser.add_argument("--loki-url")
    parser.add_argument("--loki-push-url")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    env = dict(os.environ)
    if args.loki_push_url:
        env["LOKI_PUSH_URL"] = args.loki_push_url
    push_url = release_event.loki_push_url(env, args.loki_push_url)
    query_url = loki_query_url(env, args.loki_url)
    if not push_url or not query_url:
        print(
            "LOKI_URL or LOKI_PUSH_URL is required for release-event delivery verification.",
            file=sys.stderr,
        )
        return 2

    stack_name = env.get("STACK_NAME", "aws-sdlc-containers")
    environment = env.get("DEPLOYMENT_ENVIRONMENT", "aws")
    probe_id = f"probe-{uuid4()}"
    event = build_probe_event(env, probe_id)

    release_event.push_loki(event, push_url)
    print(f"Pushed release-event delivery probe {probe_id} to {push_url}")

    if query_probe(
        loki_url=query_url,
        stack_name=stack_name,
        environment=environment,
        probe_id=probe_id,
        timeout_seconds=args.timeout_seconds,
    ):
        print(json.dumps({"ok": True, "probe_id": probe_id, "loki_url": query_url}))
        return 0

    print(
        f"Release-event delivery probe {probe_id} was not queryable in Loki.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
