import datetime
import json
import logging
from typing import Protocol
from typing import cast

from prometheus_client import Counter

from aws_sdlc_core.order import Order

logger = logging.getLogger(__name__)

ORDER_CREATED_EVENT_TYPE = "order.created.v1"

ORDER_EVENT_PUBLISH_COUNT = Counter(
    "order_events_publish_total",
    "Order event publish attempts by event type and status.",
    ["event_type", "status"],
)


class OrderEventPublishError(RuntimeError):
    pass


class OrderEventPublisher(Protocol):
    def publish_order_created(self, order: Order) -> None: ...


class SqsClient(Protocol):
    def send_message(
        self,
        *,
        QueueUrl: str,
        MessageBody: str,
        MessageGroupId: str,
        MessageDeduplicationId: str,
    ) -> object: ...


class NoopOrderEventPublisher:
    def publish_order_created(self, order: Order) -> None:
        ORDER_EVENT_PUBLISH_COUNT.labels(ORDER_CREATED_EVENT_TYPE, "skipped").inc()


class SqsOrderEventPublisher:
    def __init__(self, queue_url: str, client: SqsClient | None = None) -> None:
        self._queue_url = queue_url
        if client is None:
            import boto3

            client = cast(SqsClient, boto3.client("sqs"))
        self._client: SqsClient = client

    def publish_order_created(self, order: Order) -> None:
        event = order_created_event(order)
        event_id = str(event["event_id"])
        try:
            self._client.send_message(
                QueueUrl=self._queue_url,
                MessageBody=json.dumps(event, sort_keys=True, separators=(",", ":")),
                MessageGroupId=f"customer-{order.customer_id}",
                MessageDeduplicationId=event_id,
            )
        except Exception as exc:
            ORDER_EVENT_PUBLISH_COUNT.labels(ORDER_CREATED_EVENT_TYPE, "failed").inc()
            logger.exception(
                "order_event_publish_failed",
                extra={
                    "event_type": ORDER_CREATED_EVENT_TYPE,
                    "event_id": event_id,
                    "order_id": order.id,
                },
            )
            raise OrderEventPublishError(str(exc)) from exc

        ORDER_EVENT_PUBLISH_COUNT.labels(ORDER_CREATED_EVENT_TYPE, "succeeded").inc()
        logger.info(
            "order_event_published",
            extra={
                "event_type": ORDER_CREATED_EVENT_TYPE,
                "event_id": event_id,
                "order_id": order.id,
            },
        )


def order_created_event(order: Order) -> dict[str, object]:
    occurred_at = _isoformat(order.created_at)
    return {
        "event_type": ORDER_CREATED_EVENT_TYPE,
        "event_version": 1,
        "event_id": f"{ORDER_CREATED_EVENT_TYPE}:{order.id}",
        "idempotency_key": f"{ORDER_CREATED_EVENT_TYPE}:{order.id}",
        "occurred_at": occurred_at,
        "order": {
            "id": order.id,
            "customer_id": order.customer_id,
            "total_amount": str(order.total_amount),
            "status": order.order_status,
            "submitted_at": _isoformat(order.submitted_at),
            "created_at": occurred_at,
        },
    }


def _isoformat(value: datetime.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.UTC)
    return value.astimezone(datetime.UTC).isoformat().replace("+00:00", "Z")
