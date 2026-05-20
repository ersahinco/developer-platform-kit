# db/ Rules

Root `AGENTS.md` applies here too.

## Expand / Contract

1. Expand
2. Dual-write
3. Backfill via `apps/backfill_worker/`
4. Switch
5. Contract

Each step is a separate changeset and deployment.

## Liquibase

- Changesets in `db/changelog/` are append-only.
- IDs use `{YYYY-MM-DD}-{author}-{description}`.
- Include `rollback` where safe.
- Keep `runOnChange: false` for DDL.
- Liquibase connects directly to PostgreSQL, not PgBouncer.

## Ownership

| Capability | Tables | Primary writers |
|---|---|---|
| Order write model | `customers`, `orders`, `order_contact_email` | API, backfill worker |
| Runtime configuration | `app_runtime_config` | API admin endpoints, Liquibase seed |
| Outbox and receipts | `outbox_messages`, `order_event_receipts`, `idempotency_keys` | API, order event runtime |
| Migration and backfill control | `backfill_progress`, `DATABASECHANGELOG`, `DATABASECHANGELOGLOCK` | Liquibase, backfill worker |

Do not write across capability ownership without a documented reason.
