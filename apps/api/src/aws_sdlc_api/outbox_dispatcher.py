import argparse
import logging

from aws_sdlc_api.db import SessionLocal
from aws_sdlc_api.events import NoopOrderEventPublisher, SqsOrderEventPublisher
from aws_sdlc_api.config import settings
from aws_sdlc_adapters.db.repository import SQLAlchemyOutboxRepository
from aws_sdlc_core.outbox import dispatch_pending_outbox_messages

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch pending order event outbox messages."
    )
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    publisher = (
        NoopOrderEventPublisher()
        if settings.order_events_queue_url is None
        else SqsOrderEventPublisher(settings.order_events_queue_url)
    )

    with SessionLocal() as session:
        result = dispatch_pending_outbox_messages(
            outbox=SQLAlchemyOutboxRepository(session),
            publisher=publisher,
            limit=args.limit,
        )

    logger.info(
        "outbox_dispatch_complete",
        extra={"published": result.published, "failed": result.failed},
    )
    print(f"published={result.published} failed={result.failed}")
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
