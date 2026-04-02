-- Observability SQL: loaded by PostgreSQL at container initialisation via docker-entrypoint-initdb.d.
-- Creates backfill_progress so it exists before Liquibase runs on a fresh DB.
-- Liquibase changeset 003 is the authoritative owner — IF NOT EXISTS makes this idempotent.

CREATE TABLE IF NOT EXISTS backfill_progress (
    job_name       TEXT        PRIMARY KEY,
    last_order_id  BIGINT      NOT NULL DEFAULT 0,
    rows_processed BIGINT      NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO backfill_progress (job_name, last_order_id, rows_processed)
VALUES ('order_contact_email_backfill', 0, 0)
ON CONFLICT (job_name) DO NOTHING;
