import json
from urllib import error, parse, request

from application.outbox import OutboxMessage

EVENT_SOURCE = "aws-sdlc-containers/events"


class DaprEventPublisher:
    def __init__(
        self,
        *,
        endpoint: str,
        pubsub_name: str,
        topic: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._pubsub_name = pubsub_name
        self._topic = topic
        self._timeout_seconds = timeout_seconds

    def publish(self, message: OutboxMessage) -> None:
        topic = parse.quote(self._topic, safe="")
        pubsub = parse.quote(self._pubsub_name, safe="")
        url = f"{self._endpoint}/v1.0/publish/{pubsub}/{topic}"
        payload = cloud_event_from_outbox_message(message)
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        req = request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/cloudevents+json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                if response.status != 204:
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


def cloud_event_from_outbox_message(message: OutboxMessage) -> dict[str, object]:
    occurred_at = message.payload.get("occurred_at")
    cloud_event: dict[str, object] = {
        "specversion": "1.0",
        "id": message.event_id,
        "source": EVENT_SOURCE,
        "type": message.event_type,
        "subject": f"{message.aggregate_type}/{message.aggregate_id}",
        "datacontenttype": "application/json",
        "data": message.payload,
    }
    if isinstance(occurred_at, str):
        cloud_event["time"] = occurred_at
    return cloud_event


def payload_from_cloud_event(body: object) -> dict[str, object]:
    if not isinstance(body, dict):
        raise ValueError("Dapr event body must decode to an object")
    data = body.get("data")
    if not isinstance(data, dict):
        raise ValueError("Dapr event body must include an object data field")
    return data
