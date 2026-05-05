import json

from aws_sdlc_application.backfill import run_order_contact_email_backfill
from aws_sdlc_backfill_worker.config import settings
from aws_sdlc_infrastructure.backfill import (
    SQLAlchemyOrderContactEmailBackfillRepository,
)


def _print_event(event: dict[str, object] | str) -> None:
    if isinstance(event, str):
        print(event, flush=True)
    else:
        print(json.dumps(event, sort_keys=True), flush=True)


def run_backfill() -> None:
    repository = SQLAlchemyOrderContactEmailBackfillRepository(
        database_url=settings.required_backfill_database_url
    )
    try:
        run_order_contact_email_backfill(
            repository=repository,
            batch_size=settings.backfill_batch_size,
            sleep_seconds=settings.backfill_sleep_ms / 1000,
            max_batches=settings.backfill_max_batches,
            on_event=_print_event,
        )
    finally:
        repository.close()


def main() -> None:
    run_backfill()


if __name__ == "__main__":
    main()
