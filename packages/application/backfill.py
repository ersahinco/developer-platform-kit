import time
from dataclasses import dataclass
from typing import Callable, Protocol

ORDER_CONTACT_EMAIL_BACKFILL_JOB = "order_contact_email_backfill"


@dataclass(frozen=True)
class BackfillBatchResult:
    completed: bool
    inserted: int = 0
    last_order_id: int = 0
    rows_processed: int = 0


class OrderContactEmailBackfillRepository(Protocol):
    def process_next_batch(
        self,
        *,
        job_name: str,
        batch_size: int,
    ) -> BackfillBatchResult: ...


BackfillEventHandler = Callable[[dict[str, object] | str], None]


def run_order_contact_email_backfill(
    *,
    repository: OrderContactEmailBackfillRepository,
    batch_size: int,
    sleep_seconds: float,
    max_batches: int | None = None,
    on_event: BackfillEventHandler | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    batches_processed = 0
    while True:
        started_at = monotonic()
        result = repository.process_next_batch(
            job_name=ORDER_CONTACT_EMAIL_BACKFILL_JOB,
            batch_size=batch_size,
        )
        if result.completed:
            if on_event is not None:
                on_event(
                    {
                        "event": "backfill_complete",
                        "job_name": ORDER_CONTACT_EMAIL_BACKFILL_JOB,
                        "message": "backfill complete",
                    }
                )
            return

        batches_processed += 1
        if on_event is not None:
            on_event(
                {
                    "event": "backfill_batch",
                    "job_name": ORDER_CONTACT_EMAIL_BACKFILL_JOB,
                    "last_order_id": result.last_order_id,
                    "inserted": result.inserted,
                    "elapsed_ms": round((monotonic() - started_at) * 1000, 1),
                }
            )

        if max_batches is not None and batches_processed >= max_batches:
            if on_event is not None:
                on_event(
                    {
                        "event": "backfill_paused",
                        "job_name": ORDER_CONTACT_EMAIL_BACKFILL_JOB,
                        "reason": "max_batches",
                        "batches_processed": batches_processed,
                        "last_order_id": result.last_order_id,
                    }
                )
            return

        sleep(sleep_seconds)
