---
inclusion: fileMatch
fileMatchPattern: "{db/**,packages/infrastructure/**,tests/data/**,scripts/data/**}"
---

# Data, Schema, and Eventing Rules

Activated when working in `db/`, `packages/infrastructure/`, `tests/data/`, or `scripts/data/`.

---

## Schema Rollout — Expand/Contract Pattern

Never make a breaking schema change in a single migration. Follow the expand/contract sequence:

1. **Expand** — add new columns/tables as nullable or with defaults; old code still works
2. **Dual-write** — new code writes to both old and new shape; old code still reads old shape
3. **Backfill** — migrate existing data to the new shape (use `apps/backfill_worker/`)
4. **Switch** — new code reads from new shape only
5. **Contract** — remove old columns/tables once all readers are on the new shape

Do not skip steps under schedule pressure. Each step is a separate migration and deployment.

---

## Liquibase Rules

- Every schema change is a Liquibase changeset in `db/changelog/`
- Changesets are append-only — never modify a changeset that has already been applied
- Use `runOnChange: false` (the default) for DDL changesets
- Include a `rollback` block for every changeset that can be safely reversed
- Changeset IDs must be unique and descriptive: `{YYYY-MM-DD}-{author}-{description}`
- Liquibase connects directly to PostgreSQL — not through PgBouncer

---

## Database Capability Ownership

| Capability | Tables | Primary writers |
|---|---|---|
| Order write model | `customers`, `orders`, `order_contact_email` | API, backfill worker |
| Runtime configuration | `app_runtime_config` | API admin endpoints, Liquibase seed |
| Outbox and receipts | `outbox_messages`, `order_event_receipts`, `idempotency_keys` | API, order event runtime |
| Migration and backfill control | `backfill_progress`, `DATABASECHANGELOG`, `DATABASECHANGELOGLOCK` | Liquibase, backfill worker |
| Export outputs | S3 data hub objects | data export job |

Do not write to tables owned by another capability without a documented reason.

---

## Outbox Pattern

The durable application handoff is the database outbox (`outbox_messages`).
- Write the outbox record in the same transaction as the business state change
- The relay process reads the outbox and publishes to Dapr pub/sub
- Dapr routes to the runtime broker (SNS/SQS in AWS) — application code does not know the broker
- Idempotency keys (`idempotency_keys`) prevent duplicate processing

---

## Idempotency Requirements

Every write operation that can be retried must be idempotent:
- Use `idempotency_keys` table for operations where natural idempotency is not possible
- Document the idempotency bound in the workload or use case
- Backfill operations must be safe to rerun from any checkpoint in `backfill_progress`

---

## SQLAlchemy / Infrastructure Adapter Rules

- SQLAlchemy models and session management live in `packages/infrastructure/` only
- Repository implementations return domain objects, not ORM rows
- Keep business rules out of repository implementations — they belong in domain objects
- Use connection pooling via PgBouncer for long-running services; Liquibase connects directly
- Never expose raw SQL or ORM session objects to `packages/application/` or `apps/`

---

## Data Export Job Rules

- Export jobs must emit structured start, progress, success, and failure events
- Export outputs go to S3 (the data hub) — never to the application database
- Export jobs must be safe to rerun — document the idempotency bound
- Use the manifest pattern: write a manifest record before writing data, mark complete after

---

## Event and Message Design

- Events describe completed business facts in past tense: `OrderPlaced`, `BackfillCompleted`
- Do not publish events for every field change — only meaningful business facts
- Event payloads must be versioned — plan for old readers and old writers coexisting
- Consumers must tolerate duplicate delivery, reordering, and replay
- Dead-letter and retry behavior must be explicit — document it in the workload spec

---

## Final Check Before Committing Data/Schema Changes

- [ ] Schema change follows expand/contract — no single-step breaking migration
- [ ] Liquibase changeset is append-only with a unique descriptive ID
- [ ] Rollback block included where safe
- [ ] Idempotency documented for retryable operations
- [ ] Repository returns domain objects, not ORM rows
- [ ] Event payloads are versioned and tolerate duplicate delivery
- [ ] `make runtime-conformance` passes after migration
