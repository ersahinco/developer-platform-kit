# db/ — Schema and Migration Rules

Scoped rules for `db/` (Liquibase, PgBouncer, bootstrap SQL).
The cross-tool base rules in root `AGENTS.md` apply here too.

---

## Expand/Contract — Always

Never make a breaking schema change in a single migration. The sequence is:

1. **Expand** — add nullable columns/tables; old code still works
2. **Dual-write** — new code writes both old and new shape
3. **Backfill** — migrate existing data via `apps/backfill_worker/`
4. **Switch** — new code reads new shape only
5. **Contract** — remove old columns/tables

Each step is a separate changeset and a separate deployment.

---

## Liquibase Rules

- Every schema change is a changeset in `db/changelog/` — append-only, never modify applied changesets
- Changeset IDs: `{YYYY-MM-DD}-{author}-{description}` — unique and descriptive
- Include a `rollback` block for every changeset that can be safely reversed
- `runOnChange: false` (the default) for all DDL changesets
- Liquibase connects directly to PostgreSQL — not through PgBouncer

---

## Database Capability Ownership

| Capability | Tables | Primary writers |
|---|---|---|
| Order write model | `customers`, `orders`, `order_contact_email` | API, backfill worker |
| Runtime configuration | `app_runtime_config` | API admin endpoints, Liquibase seed |
| Outbox and receipts | `outbox_messages`, `order_event_receipts`, `idempotency_keys` | API, order event runtime |
| Migration and backfill control | `backfill_progress`, `DATABASECHANGELOG`, `DATABASECHANGELOGLOCK` | Liquibase, backfill worker |

Do not write to tables owned by another capability without a documented reason.

---

## PgBouncer

- Long-running services connect through PgBouncer
- Liquibase connects directly — not through PgBouncer
- PgBouncer assets live in `db/pgbouncer/`
