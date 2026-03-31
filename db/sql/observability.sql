-- Observability SQL: loaded by PostgreSQL at container initialisation via docker-entrypoint-initdb.d
-- Creates and seeds the backfill_progress table used by the backfill worker as a checkpoint cursor.
-- This table is intentionally created outside Liquibase so it exists before any changeset runs.

CREATE TABLE IF NOT EXISTS backfill_progress (
    job_name      TEXT        PRIMARY KEY,
    last_order_id BIGINT      NOT NULL DEFAULT 0,
    rows_processed BIGINT     NOT NULL DEFAULT 0,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the initial checkpoint row for the order_contact_email backfill job.
INSERT INTO backfill_progress (job_name, last_order_id, rows_processed)
VALUES ('order_contact_email_backfill', 0, 0)
ON CONFLICT (job_name) DO NOTHING;
