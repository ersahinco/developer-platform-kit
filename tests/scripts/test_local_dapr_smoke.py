from __future__ import annotations

import pytest

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


def test_wait_for_dapr_metadata_accepts_subscription_after_initial_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = {
        "components": [{"name": "async-events-pubsub", "type": "pubsub.redis"}],
        "subscriptions": [],
    }
    ready = {
        "components": [{"name": "async-events-pubsub", "type": "pubsub.redis"}],
        "subscriptions": [
            {
                "pubsubname": "async-events-pubsub",
                "topic": "async-events-v1.fifo",
                "rules": [{"path": "/internal/events/consume"}],
            }
        ],
    }
    responses = iter([missing, ready])
    monkeypatch.setattr(
        local_dapr_smoke, "load_dapr_metadata", lambda _: next(responses)
    )
    monkeypatch.setattr(local_dapr_smoke.time, "sleep", lambda _: None)

    metadata = local_dapr_smoke.wait_for_dapr_metadata(
        "http://localhost:3500",
        pubsub_name="async-events-pubsub",
        topic="async-events-v1.fifo",
        route="/internal/events/consume",
        timeout_seconds=1.0,
        poll_interval_seconds=0.0,
    )

    assert metadata == ready


def test_wait_for_dapr_metadata_times_out_with_missing_subscription(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    metadata = {
        "components": [{"name": "async-events-pubsub", "type": "pubsub.redis"}],
        "subscriptions": [],
    }
    monkeypatch.setattr(local_dapr_smoke, "load_dapr_metadata", lambda _: metadata)
    monotonic_values = iter([0.0, 1.0])
    monkeypatch.setattr(
        local_dapr_smoke.time, "monotonic", lambda: next(monotonic_values)
    )

    with pytest.raises(RuntimeError, match="readiness timeout"):
        local_dapr_smoke.wait_for_dapr_metadata(
            "http://localhost:3500",
            pubsub_name="async-events-pubsub",
            topic="async-events-v1.fifo",
            route="/internal/events/consume",
            timeout_seconds=0.5,
            poll_interval_seconds=0.0,
        )

    assert "Dapr metadata does not include subscription" in capsys.readouterr().err


def test_wait_for_app_readiness_accepts_ready_after_initial_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter([{"status": "unready"}, {"status": "ready"}])
    monkeypatch.setattr(
        local_dapr_smoke,
        "load_app_readiness",
        lambda _endpoint, *, app_id: next(responses),
    )
    monkeypatch.setattr(local_dapr_smoke.time, "sleep", lambda _: None)

    readiness = local_dapr_smoke.wait_for_app_readiness(
        "http://localhost:3500",
        app_id="event-consumer",
        timeout_seconds=1.0,
        poll_interval_seconds=0.0,
    )

    assert readiness == {"status": "ready"}


def test_wait_for_app_readiness_times_out_with_last_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        local_dapr_smoke,
        "load_app_readiness",
        lambda _endpoint, *, app_id: {"status": "unready"},
    )
    monotonic_values = iter([0.0, 1.0])
    monkeypatch.setattr(
        local_dapr_smoke.time, "monotonic", lambda: next(monotonic_values)
    )

    with pytest.raises(RuntimeError, match="Dapr app channel did not report ready"):
        local_dapr_smoke.wait_for_app_readiness(
            "http://localhost:3500",
            app_id="event-consumer",
            timeout_seconds=0.5,
            poll_interval_seconds=0.0,
        )
