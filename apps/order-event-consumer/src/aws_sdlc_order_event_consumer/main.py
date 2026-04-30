import datetime
import json
import time
from typing import Any, Protocol, cast

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from aws_sdlc_adapters.db.repository import (
    SQLAlchemyOrderEventReceiptRepository,
    SQLAlchemyOutboxRepository,
)
from aws_sdlc_core.outbox import OutboxMessage, dispatch_pending_outbox_messages
from aws_sdlc_order_event_consumer.config import settings


class SqsClient(Protocol):
    def send_message(
        self,
        *,
        QueueUrl: str,
        MessageBody: str,
        MessageGroupId: str,
        MessageDeduplicationId: str,
    ) -> object: ...

    def receive_message(
        self,
        *,
        QueueUrl: str,
        MaxNumberOfMessages: int,
        WaitTimeSeconds: int,
        VisibilityTimeout: int,
    ) -> dict[str, Any]: ...

    def delete_message(self, *, QueueUrl: str, ReceiptHandle: str) -> object: ...


class SqsOutboxPublisher:
    def __init__(self, queue_url: str, client: SqsClient) -> None:
        self._queue_url = queue_url
        self._client = client

    def publish(self, message: OutboxMessage) -> None:
        self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=json.dumps(
                message.payload, sort_keys=True, separators=(",", ":")
            ),
            MessageGroupId=message.message_group_id,
            MessageDeduplicationId=message.message_deduplication_id,
        )


def _sqs_client() -> SqsClient:
    import boto3

    return cast(SqsClient, boto3.client("sqs"))


def relay_outbox_once(
    session: Session,
    *,
    queue_url: str,
    client: SqsClient,
    limit: int,
) -> int:
    result = dispatch_pending_outbox_messages(
        outbox=SQLAlchemyOutboxRepository(session),
        publisher=SqsOutboxPublisher(queue_url, client),
        limit=limit,
    )
    print(
        json.dumps(
            {
                "event": "outbox_relay",
                "published": result.published,
                "failed": result.failed,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return result.published + result.failed


def consume_order_events_once(
    session: Session,
    *,
    queue_url: str,
    client: SqsClient,
    max_messages: int,
    wait_seconds: int,
    visibility_timeout_seconds: int,
) -> int:
    response = client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=wait_seconds,
        VisibilityTimeout=visibility_timeout_seconds,
    )
    messages = response.get("Messages", [])
    if not isinstance(messages, list):
        return 0

    processed = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        receipt_handle = message.get("ReceiptHandle")
        body = message.get("Body")
        should_delete = False
        try:
            if not isinstance(body, str):
                raise ValueError("SQS message body must be a JSON string")
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("SQS message body must decode to an object")
            result = SQLAlchemyOrderEventReceiptRepository(session).record(
                payload,
                now=datetime.datetime.now(tz=datetime.UTC),
            )
            should_delete = True
            processed += 1
            print(
                json.dumps(
                    {
                        "event": "order_event_consumed",
                        "event_id": result.event_id,
                        "status": result.status,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        except Exception as exc:
            session.rollback()
            print(
                json.dumps(
                    {
                        "event": "order_event_consume_failed",
                        "error": str(exc),
                        "delete": False,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

        if should_delete and isinstance(receipt_handle, str):
            client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

    return processed


def run_worker(client: SqsClient | None = None) -> None:
    sqs = client or _sqs_client()
    queue_url = settings.required_queue_url
    engine = create_engine(str(settings.database_url), pool_pre_ping=True)
    SessionLocal = sessionmaker(engine)
    try:
        while True:
            work_done = 0
            with SessionLocal() as session:
                if settings.order_events_worker_mode in ("relay", "both"):
                    work_done += relay_outbox_once(
                        session,
                        queue_url=queue_url,
                        client=sqs,
                        limit=settings.order_events_relay_batch_size,
                    )
                if settings.order_events_worker_mode in ("consumer", "both"):
                    work_done += consume_order_events_once(
                        session,
                        queue_url=queue_url,
                        client=sqs,
                        max_messages=settings.order_events_receive_max_messages,
                        wait_seconds=settings.order_events_receive_wait_seconds,
                        visibility_timeout_seconds=(
                            settings.order_events_visibility_timeout_seconds
                        ),
                    )
            if settings.order_events_worker_run_once:
                break
            if work_done == 0:
                time.sleep(settings.order_events_idle_sleep_seconds)
    finally:
        engine.dispose()


if __name__ == "__main__":
    run_worker()
