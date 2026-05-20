---
inclusion: fileMatch
fileMatchPattern: "{db/**,packages/infrastructure/**,tests/data/**,scripts/data/**}"
---

# Data, Schema, and Eventing Rules

Activated when working in `db/`, `packages/infrastructure/`, `tests/data/`, or `scripts/data/`.

## Schema Rollout

1. Expand
2. Dual-write
3. Backfill via `apps/backfill_worker/`
4. Switch
5. Contract

Each step is a separate migration and deployment.

## Rules

- Liquibase changesets in `db/changelog/` are append-only, use `runOnChange: false`, and include `rollback` where safe.
- Use changeset IDs `{YYYY-MM-DD}-{author}-{description}`.
- Liquibase connects directly to PostgreSQL, not PgBouncer.
- The durable app handoff is `outbox_messages`.
- Retryable writes must be idempotent. Use `idempotency_keys` where needed.
- Repositories return domain objects, not ORM rows.
- Export jobs emit structured events, write raw data before manifest, and are safe to rerun.
- Events are versioned business facts; consumers tolerate duplicates, replay, and reordering.
