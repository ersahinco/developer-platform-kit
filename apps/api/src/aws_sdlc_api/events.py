import json
import logging
from typing import Protocol
from typing import cast

from prometheus_client import Counter

from aws_sdlc_core.order import Order
from aws_sdlc_core.order_events import ORDER_CREATED_EVENT_TYPE, order_created_event
from aws_sdlc_core.order_events import order_created_message
from aws_sdlc_core.outbox import OutboxMessage

logger = logging.getLogger(__name__)

__all__ = [
    "NoopOrderEventPublisher",
    "OrderEventPublishError",
    "OrderEventPublisher",
    "SqsOrderEventPublisher",
    "order_created_event",
]

ORDER_EVENT_PUBLISH_COUNT = Counter(
    "order_events_publish_total",
    "Order event publish attempts by event type and status.",
    ["event_type", "status"],
)


class OrderEventPublishError(RuntimeError):
    pass


class OrderEventPublisher(Protocol):
    def publish_order_created(self, order: Order) -> None: ...

    def publish(self, message: OutboxMessage) -> None: ...


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
        self.publish(_message_from_order(order))

    def publish(self, message: OutboxMessage) -> None:
        ORDER_EVENT_PUBLISH_COUNT.labels(ORDER_CREATED_EVENT_TYPE, "skipped").inc()


class SqsOrderEventPublisher:
    def __init__(self, queue_url: str, client: SqsClient | None = None) -> None:
        self._queue_url = queue_url
        if client is None:
            import boto3

            client = cast(SqsClient, boto3.client("sqs"))
        self._client: SqsClient = client

    def publish_order_created(self, order: Order) -> None:
        self.publish(_message_from_order(order))

    def publish(self, message: OutboxMessage) -> None:
        try:
            self._client.send_message(
                QueueUrl=self._queue_url,
                MessageBody=json.dumps(
                    message.payload, sort_keys=True, separators=(",", ":")
                ),
                MessageGroupId=message.message_group_id,
                MessageDeduplicationId=message.message_deduplication_id,
            )
        except Exception as exc:
            ORDER_EVENT_PUBLISH_COUNT.labels(message.event_type, "failed").inc()
            logger.exception(
                "order_event_publish_failed",
                extra={
                    "event_type": message.event_type,
                    "event_id": message.event_id,
                    "aggregate_id": message.aggregate_id,
                },
            )
            raise OrderEventPublishError(str(exc)) from exc

        ORDER_EVENT_PUBLISH_COUNT.labels(message.event_type, "succeeded").inc()
        logger.info(
            "order_event_published",
            extra={
                "event_type": message.event_type,
                "event_id": message.event_id,
                "aggregate_id": message.aggregate_id,
            },
        )


def _message_from_order(order: Order) -> OutboxMessage:
    message = order_created_message(order)
    return OutboxMessage(
        id=0,
        event_type=message.event_type,
        event_id=message.event_id,
        aggregate_type=message.aggregate_type,
        aggregate_id=message.aggregate_id,
        message_group_id=message.message_group_id,
        message_deduplication_id=message.message_deduplication_id,
        payload=message.payload,
        attempt_count=0,
    )
