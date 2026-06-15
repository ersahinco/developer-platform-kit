from __future__ import annotations

import datetime
import json
import os
import sys
import time
import uuid
from typing import Any
from urllib import error, request

from sqlalchemy import Engine, create_engine, text


DEFAULT_DAPR_HTTP_ENDPOINT = "http://localhost:3500"
DEFAULT_DATABASE_URL = (
    "postgresql://postgres:postgres@localhost:6432/aws_sdlc_containers"
)
DEFAULT_PUBSUB_NAME = "async-events-pubsub"
DEFAULT_TOPIC = "async-events-v1.fifo"
DEFAULT_ROUTE = "/internal/events/consume"
DEFAULT_APP_ID = "event-consumer"
DEFAULT_METADATA_TIMEOUT_SECONDS = 20.0
DEFAULT_METADATA_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_APP_READY_TIMEOUT_SECONDS = 30.0
DEFAULT_APP_READY_POLL_INTERVAL_SECONDS = 0.5


def build_cloud_event(*, event_id: str, occurred_at: str) -> dict[str, object]:
    payload = {
        "event_type": "order.created.v1",
        "event_version": 1,
        "event_id": event_id,
        "idempotency_key": event_id,
        "aggregate_type": "order",
        "aggregate_id": 260528,
        "occurred_at": occurred_at,
        "order": {
            "id": 260528,
            "customer_id": 1,
            "total_amount": "10.00",
            "status": "SUBMITTED",
            "submitted_at": occurred_at,
            "created_at": occurred_at,
        },
    }
    return {
        "specversion": "1.0",
        "id": event_id,
        "source": "aws-sdlc-containers/events",
        "type": "order.created.v1",
        "datacontenttype": "application/json",
        "data": payload,
    }


def load_dapr_metadata(endpoint: str) -> dict[str, Any]:
    url = f"{endpoint.rstrip('/')}/v1.0/metadata"
    try:
        with request.urlopen(url, timeout=5.0) as response:
            body = response.read().decode("utf-8")
    except error.URLError as exc:
        raise RuntimeError(
            f"Could not reach local Dapr sidecar at {url}. Run `make dapr-up` first."
        ) from exc
    metadata = json.loads(body)
    if not isinstance(metadata, dict):
        raise RuntimeError("Dapr metadata response must be a JSON object.")
    return metadata


def dapr_metadata_errors(
    metadata: dict[str, Any],
    *,
    pubsub_name: str,
    topic: str,
    route: str,
) -> list[str]:
    errors: list[str] = []
    components = metadata.get("components", [])
    if not any(
        isinstance(component, dict)
        and component.get("name") == pubsub_name
        and str(component.get("type", "")).startswith("pubsub.")
        for component in components
        if isinstance(component, dict)
    ):
        errors.append(
            f"Dapr metadata does not include pub/sub component {pubsub_name!r}."
        )

    subscriptions = metadata.get("subscriptions", [])
    has_subscription = False
    for subscription in subscriptions:
        if not isinstance(subscription, dict):
            continue
        rules = subscription.get("rules", [])
        has_route = any(
            isinstance(rule, dict) and rule.get("path") == route for rule in rules
        )
        if (
            subscription.get("pubsubname") == pubsub_name
            and subscription.get("topic") == topic
            and has_route
        ):
            has_subscription = True
            break
    if not has_subscription:
        errors.append(
            f"Dapr metadata does not include subscription {pubsub_name}/{topic} -> {route}."
        )
    return errors


def wait_for_dapr_metadata(
    endpoint: str,
    *,
    pubsub_name: str,
    topic: str,
    route: str,
    timeout_seconds: float = DEFAULT_METADATA_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_METADATA_POLL_INTERVAL_SECONDS,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_errors: list[str] = []
    while True:
        metadata = load_dapr_metadata(endpoint)
        last_errors = dapr_metadata_errors(
            metadata,
            pubsub_name=pubsub_name,
            topic=topic,
            route=route,
        )
        if not last_errors:
            return metadata
        if time.monotonic() >= deadline:
            for message in last_errors:
                print(message, file=sys.stderr)
            raise RuntimeError(
                "Dapr sidecar metadata did not expose the expected local "
                "subscription before the readiness timeout."
            )
        time.sleep(poll_interval_seconds)


def load_app_readiness(endpoint: str, *, app_id: str) -> dict[str, Any]:
    url = f"{endpoint.rstrip('/')}/v1.0/invoke/{app_id}/method/ready"
    try:
        with request.urlopen(url, timeout=5.0) as response:
            body = response.read().decode("utf-8")
    except error.URLError as exc:
        raise RuntimeError(
            f"Could not reach local Dapr app channel for {app_id!r} at {url}."
        ) from exc
    readiness = json.loads(body)
    if not isinstance(readiness, dict):
        raise RuntimeError("Dapr app readiness response must be a JSON object.")
    return readiness


def wait_for_app_readiness(
    endpoint: str,
    *,
    app_id: str,
    timeout_seconds: float = DEFAULT_APP_READY_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_APP_READY_POLL_INTERVAL_SECONDS,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_readiness: dict[str, Any] | None = None
    while True:
        try:
            readiness = load_app_readiness(endpoint, app_id=app_id)
        except RuntimeError:
            readiness = None
        if readiness is not None:
            last_readiness = readiness
            if readiness.get("status") == "ready":
                return readiness
        if time.monotonic() >= deadline:
            raise RuntimeError(
                "Dapr app channel did not report ready before the smoke timeout: "
                f"{last_readiness}"
            )
        time.sleep(poll_interval_seconds)


def publish_cloud_event(
    endpoint: str,
    *,
    pubsub_name: str,
    topic: str,
    cloud_event: dict[str, object],
) -> None:
    url = f"{endpoint.rstrip('/')}/v1.0/publish/{pubsub_name}/{topic}"
    body = json.dumps(cloud_event, sort_keys=True, separators=(",", ":")).encode()
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/cloudevents+json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=5.0) as response:
            if response.status not in {200, 204}:
                response_body = response.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"Dapr publish returned {response.status}: {response_body}"
                )
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Dapr publish returned {exc.code}: {response_body}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Dapr publish failed: {exc.reason}") from exc


def fetch_receipt(engine: Engine, event_id: str) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    "select event_id, status, duplicate_count "
                    "from event_receipts where event_id = :event_id"
                ),
                {"event_id": event_id},
            )
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None


def wait_for_receipt(
    database_url: str,
    *,
    event_id: str,
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 0.5,
) -> dict[str, Any]:
    engine = create_engine(database_url, pool_pre_ping=True)
    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            receipt = fetch_receipt(engine, event_id)
            if receipt is not None:
                return receipt
            time.sleep(poll_interval_seconds)
    finally:
        engine.dispose()
    raise RuntimeError(
        f"Event {event_id!r} was published but no event_receipts row appeared."
    )


def run() -> int:
    endpoint = os.environ.get("DAPR_HTTP_ENDPOINT", DEFAULT_DAPR_HTTP_ENDPOINT)
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    pubsub_name = os.environ.get("DAPR_PUBSUB_NAME", DEFAULT_PUBSUB_NAME)
    topic = os.environ.get("DAPR_TOPIC", DEFAULT_TOPIC)
    route = os.environ.get("DAPR_SUBSCRIPTION_ROUTE", DEFAULT_ROUTE)
    app_id = os.environ.get("DAPR_APP_ID", DEFAULT_APP_ID)
    metadata_timeout_seconds = float(
        os.environ.get(
            "DAPR_METADATA_TIMEOUT_SECONDS",
            str(DEFAULT_METADATA_TIMEOUT_SECONDS),
        )
    )
    metadata_poll_interval_seconds = float(
        os.environ.get(
            "DAPR_METADATA_POLL_INTERVAL_SECONDS",
            str(DEFAULT_METADATA_POLL_INTERVAL_SECONDS),
        )
    )
    app_ready_timeout_seconds = float(
        os.environ.get(
            "DAPR_APP_READY_TIMEOUT_SECONDS",
            str(DEFAULT_APP_READY_TIMEOUT_SECONDS),
        )
    )
    app_ready_poll_interval_seconds = float(
        os.environ.get(
            "DAPR_APP_READY_POLL_INTERVAL_SECONDS",
            str(DEFAULT_APP_READY_POLL_INTERVAL_SECONDS),
        )
    )

    try:
        wait_for_dapr_metadata(
            endpoint,
            pubsub_name=pubsub_name,
            topic=topic,
            route=route,
            timeout_seconds=metadata_timeout_seconds,
            poll_interval_seconds=metadata_poll_interval_seconds,
        )
        wait_for_app_readiness(
            endpoint,
            app_id=app_id,
            timeout_seconds=app_ready_timeout_seconds,
            poll_interval_seconds=app_ready_poll_interval_seconds,
        )
    except RuntimeError:
        return 1

    occurred_at = datetime.datetime.now(tz=datetime.UTC).isoformat()
    event_id = f"order.created.v1:local-smoke-{uuid.uuid4().hex}"
    publish_cloud_event(
        endpoint,
        pubsub_name=pubsub_name,
        topic=topic,
        cloud_event=build_cloud_event(event_id=event_id, occurred_at=occurred_at),
    )
    receipt = wait_for_receipt(database_url, event_id=event_id)
    if receipt.get("status") not in {"processed", "duplicate", "ignored_stale"}:
        raise RuntimeError(f"Unexpected event receipt status: {receipt}")

    print(
        json.dumps(
            {
                "event": "local_dapr_smoke_succeeded",
                "event_id": receipt["event_id"],
                "status": receipt["status"],
                "pubsub": pubsub_name,
                "topic": topic,
                "route": route,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
