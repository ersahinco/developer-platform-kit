from sqlalchemy import create_engine, text

from application.backfill import BackfillBatchResult


class SQLAlchemyOrderContactEmailBackfillRepository:
    def __init__(self, *, database_url: str) -> None:
        self._engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
        )

    def close(self) -> None:
        self._engine.dispose()

    def process_next_batch(
        self,
        *,
        job_name: str,
        batch_size: int,
    ) -> BackfillBatchResult:
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT last_order_id, rows_processed "
                    "FROM backfill_progress WHERE job_name = :job"
                ),
                {"job": job_name},
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
                    "batch_size": batch_size,
                },
            ).fetchall()

            if not batch:
                return BackfillBatchResult(completed=True)

            conn.execute(
                text(
                    "INSERT INTO order_contact_email (order_id, billing_email, source) "
                    "VALUES (:order_id, :billing_email, 'backfill') "
                    "ON CONFLICT (order_id) DO NOTHING"
                ),
                [{"order_id": r.id, "billing_email": r.billing_email} for r in batch],
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
                {"job": job_name, "last_id": new_last, "processed": new_processed},
            )

            return BackfillBatchResult(
                completed=False,
                inserted=len(batch),
                last_order_id=new_last,
                rows_processed=new_processed,
            )
