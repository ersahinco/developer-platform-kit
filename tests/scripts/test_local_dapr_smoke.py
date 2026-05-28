from __future__ import annotations

from scripts.platform import local_dapr_smoke


def test_build_cloud_event_matches_consumer_payload_contract() -> None:
    cloud_event = local_dapr_smoke.build_cloud_event(
        event_id="order.created.v1:test",
        occurred_at="2026-05-28T18:00:00+00:00",
    )

    assert cloud_event["source"] == "aws-sdlc-containers/events"
    assert cloud_event["type"] == "order.created.v1"
    payload = cloud_event["data"]
    assert isinstance(payload, dict)
    assert payload["event_id"] == "order.created.v1:test"
    assert payload["idempotency_key"] == "order.created.v1:test"
    assert payload["aggregate_type"] == "order"
    assert payload["occurred_at"] == "2026-05-28T18:00:00+00:00"


def test_dapr_metadata_errors_accepts_expected_local_subscription() -> None:
    metadata = {
        "components": [
            {
                "name": "async-events-pubsub",
                "type": "pubsub.redis",
                "version": "v1",
            }
        ],
        "subscriptions": [
            {
                "pubsubname": "async-events-pubsub",
                "topic": "async-events-v1.fifo",
                "rules": [{"path": "/internal/events/consume"}],
            }
        ],
    }

    assert (
        local_dapr_smoke.dapr_metadata_errors(
            metadata,
            pubsub_name="async-events-pubsub",
            topic="async-events-v1.fifo",
            route="/internal/events/consume",
        )
        == []
    )


def test_dapr_metadata_errors_explains_missing_subscription() -> None:
    metadata = {
        "components": [{"name": "async-events-pubsub", "type": "pubsub.redis"}],
        "subscriptions": [],
    }

    errors = local_dapr_smoke.dapr_metadata_errors(
        metadata,
        pubsub_name="async-events-pubsub",
        topic="async-events-v1.fifo",
        route="/internal/events/consume",
    )

    assert errors == [
        "Dapr metadata does not include subscription async-events-pubsub/"
        "async-events-v1.fifo -> /internal/events/consume."
    ]
