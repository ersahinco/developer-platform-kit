# Architecture

## Why hexagonal architecture for a migration example?

The migration requires the app to change *where* it reads and writes data at runtime — without a redeploy, without touching the HTTP layer. That's only possible if the HTTP layer doesn't know about SQL.

`ports.py` defines what the domain needs, not how it's done:

```python
class OrderRepository(abc.ABC):
    def get_order(self, order_id: int) -> Order | None: ...

class ConfigStore(abc.ABC):
    def get_read_mode(self) -> str: ...
    def set_read_mode(self, mode: str) -> None: ...
```

`main.py` calls the port. It has no idea which table `get_order` reads from:

```python
order = repo.get_order(order_id)
```

The routing logic lives entirely in `repository.py`:

```python
if self._config_store.get_read_mode() == "new":
    contact = self._session.get(OrderContactEmailModel, order_id)
    resolved_email = contact.billing_email if contact else None
else:
    resolved_email = order_row.billing_email  # legacy column
```

When `POST /admin/read-mode {"mode": "new"}` is called, `set_read_mode` writes to `app_runtime_config` and invalidates the in-process cache. The next request reads the new value. The route handler never changes.

Without this separation, the `if read_mode == "new"` branch would live in the route — mixing HTTP and storage concerns, and making the switch a deploy instead of an API call.

---

## Layer map

```
adapters/api/        — HTTP boundary (FastAPI routes, Pydantic schemas)
                           ↓ calls ports only, no SQLAlchemy imports
domain/              — Order entity, abstract ports (pure Python)
                           ↓ implemented by
adapters/db/         — SQLAlchemy models, repository (all SQL lives here)
db.py                — engine, session factory, get_db()
```

---

## Runtime config cache

`_ReadModeCache` in `repository.py` is a process-level cache with a 5-second TTL and double-checked locking. On a cache miss, one thread queries the DB while others wait on the lock. When the lock is released, waiting threads see a warm cache and return without a DB hit — N concurrent misses cause exactly one DB query.

`set_read_mode` calls `invalidate()` immediately so the next request re-reads from the DB rather than waiting for TTL expiry.

In production, `invalidate()` only clears the local process cache. Other instances serve stale values until their TTL expires. The fix is pub/sub invalidation (Redis, SNS) — each instance drops its cache on receipt of the event. The cache is entirely inside `SQLAlchemyConfigStore`, so swapping the mechanism is a one-file change with no impact on the ports or routes.

---

## Backfill worker

Separate Docker service, no FastAPI dependency. Runs once and exits.

Each batch:
1. Read checkpoint from `backfill_progress` inside the transaction.
2. `SELECT id, billing_email FROM orders WHERE id > :last_id AND billing_email IS NOT NULL ORDER BY id LIMIT :batch_size`
3. `INSERT INTO order_contact_email ... ON CONFLICT (order_id) DO NOTHING` — safe to re-run.
4. Update checkpoint in the same transaction — cursor only advances on successful insert.
5. Sleep `BACKFILL_SLEEP_MS` ms before next batch.

The checkpoint + same-transaction update means a crash mid-batch replays the batch cleanly on restart.

---

## Contract changeset precondition

`003-contract-drop-orders-billing-email.yaml` uses a Liquibase `sqlCheck` precondition:

```yaml
preConditions:
  - onFail: HALT
    sqlCheck:
      expectedResult: new
      sql: SELECT value FROM app_runtime_config WHERE key = 'READ_MODE'
```

If `READ_MODE != new`, Liquibase halts without marking the changeset as run. Running `liquibase update` again after switching reads will apply it. This is the database enforcing that no reads point at the column before it's dropped.

---

## What's intentionally omitted

- Feedback-driven backfill throttling (replication lag, primary CPU load)
- Rolling deploy coordination for `WRITE_MODE` across multiple instances
- Pub/sub cache invalidation for `READ_MODE` across instances
- `CREATE INDEX CONCURRENTLY` failure detection (check `pg_indexes` for `INVALID`)
- PgBouncer for the backfill worker
- Secrets management (`DATABASE_URL` in `.env` is local-only)
- DB snapshot before the Contract phase
