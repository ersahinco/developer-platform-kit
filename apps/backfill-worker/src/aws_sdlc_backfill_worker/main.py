import json
import time

from sqlalchemy import create_engine, text

from aws_sdlc_backfill_worker.config import settings

JOB_NAME = "order_contact_email_backfill"


def run_backfill() -> None:
    # Worker connects directly to Postgres — bypasses pgbouncer.
    # Backfill uses long-running transactions that are incompatible with
    # pgbouncer's transaction-mode pool.
    engine = create_engine(
        settings.required_backfill_database_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        batches_processed = 0
        completed = False
        while True:
            start = time.monotonic()

            with engine.begin() as conn:
                # Re-read checkpoint inside the transaction — ensures consistency
                # on restart after a mid-batch crash.
                row = conn.execute(
                    text(
                        "SELECT last_order_id, rows_processed "
                        "FROM backfill_progress WHERE job_name = :job"
                    ),
                    {"job": JOB_NAME},
                ).fetchone()
                last_order_id = row.last_order_id if row else 0
                rows_processed = row.rows_processed if row else 0

                batch = conn.execute(
                    text(
                        "SELECT id, billing_email FROM orders "
                        "WHERE id > :last_id "
                        "AND billing_email IS NOT NULL "
                        "ORDER BY id "
                        "LIMIT :batch_size"
                    ),
                    {
                        "last_id": last_order_id,
                        "batch_size": settings.backfill_batch_size,
                    },
                ).fetchall()

                if not batch:
                    completed = True
                    break

                conn.execute(
                    text(
                        "INSERT INTO order_contact_email (order_id, billing_email, source) "
                        "VALUES (:order_id, :billing_email, 'backfill') "
                        "ON CONFLICT (order_id) DO NOTHING"
                    ),
                    [
                        {"order_id": r.id, "billing_email": r.billing_email}
                        for r in batch
                    ],
                )

                new_last = batch[-1].id
                new_processed = rows_processed + len(batch)

                conn.execute(
                    text(
                        "INSERT INTO backfill_progress (job_name, last_order_id, rows_processed) "
                        "VALUES (:job, :last_id, :processed) "
                        "ON CONFLICT (job_name) DO UPDATE "
                        "SET last_order_id = :last_id, rows_processed = :processed, updated_at = NOW()"
                    ),
                    {"job": JOB_NAME, "last_id": new_last, "processed": new_processed},
                )

                last_order_id = new_last
                rows_processed = new_processed

            elapsed_ms = (time.monotonic() - start) * 1000
            batches_processed += 1
            print(
                json.dumps(
                    {
                        "last_order_id": last_order_id,
                        "inserted": len(batch),
                        "elapsed_ms": round(elapsed_ms, 1),
                    }
                ),
                flush=True,
            )

            if (
                settings.backfill_max_batches is not None
                and batches_processed >= settings.backfill_max_batches
            ):
                print(
                    json.dumps(
                        {
                            "event": "backfill_paused",
                            "reason": "max_batches",
                            "batches_processed": batches_processed,
                            "last_order_id": last_order_id,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
                break

            time.sleep(settings.backfill_sleep_ms / 1000)

        if completed:
            print("backfill complete", flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    run_backfill()
