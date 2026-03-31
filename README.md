# db-migration-example

A fully-runnable local example of the **expand → dual-write → backfill → switch → contract** pattern for zero/low-downtime schema migrations.

The concrete migration: moving `orders.billing_email` into a dedicated `order_contact_email` table — without downtime, without locking the table, and without a flag day.

---

## What this demonstrates

| Phase | Mechanism | Key files |
|---|---|---|
| Expand | Additive DDL — new table + index, nothing removed | `db/changelog/001-expand-order-contact-email.yaml` |
| Dual-write | `WRITE_MODE=dual` — app writes to both tables | `app/src/adapters/db/repository.py` |
| Backfill | Standalone worker copies historic rows in batches | `worker/src/backfill.py` |
| Switch | `POST /admin/read-mode` flips reads at runtime, no redeploy | `scripts/switch_read_mode.py` |
| Contract | Guarded DDL — drops old column only when `READ_MODE=new` | `db/changelog/003-contract-drop-orders-billing-email.yaml` |

---

## How it works

The app controls migration behavior through two environment variables — `WRITE_MODE` and `READ_MODE` — without any redeploy. This is possible because the HTTP layer (`main.py`) never touches SQL directly. It calls abstract ports (`OrderRepository`, `ConfigStore`), and the concrete implementation in `repository.py` decides which table to read from or write to based on the current mode.

Flipping `POST /admin/read-mode {"mode": "new"}` writes to `app_runtime_config` in the database and takes effect on the next request. The route handler is unchanged.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design rationale.

---

- Docker Desktop — [install](https://docs.docker.com/desktop/install/mac-install/)
- Python 3.12+ — `brew install python@3.12`
- `uv` — `brew install uv`

---

## Project layout

```
data-ai/db-migration-example/
├── app/src/
│   ├── config.py                 # pydantic-settings: WRITE_MODE, READ_MODE, DATABASE_URL
│   ├── db.py                     # SQLAlchemy engine + get_db()
│   ├── domain/
│   │   ├── order.py              # Order entity — pure Python
│   │   └── ports.py              # Abstract interfaces: OrderRepository, ConfigStore
│   └── adapters/
│       ├── api/main.py           # FastAPI routes
│       └── db/repository.py      # Dual-write + read-mode routing lives here
├── worker/src/
│   ├── backfill.py               # Checkpoint-based batch backfill
│   └── metrics.py                # Structured JSON batch logging
├── db/changelog/
│   ├── 000-bootstrap.yaml        # customers + orders tables
│   ├── 001-expand-*.yaml         # Expand phase
│   ├── 002-switch-*.yaml         # app_runtime_config + READ_MODE seed
│   └── 003-contract-*.yaml       # Contract phase (guarded by precondition)
├── scripts/                      # seed, smoke test, switch, verify, upgrade-path
├── tests/                        # pytest phase-aware integration tests
├── .env.example                  # All env vars with safe local defaults
└── docker-compose.yml
```

---

## Environment variables

| Variable | Values | Effect |
|---|---|---|
| `WRITE_MODE` | `legacy` / `dual` / `new` | Where `POST /orders` writes email data |
| `READ_MODE` | `legacy` / `new` | Where `GET /orders/{id}` reads email from |

`READ_MODE` is also switchable at runtime via `POST /admin/read-mode` — no restart needed.

Copy the example env file once:

```bash
cp .env.example .env
```

> **Host vs container `DATABASE_URL`** — `.env` uses `db` as the hostname, which resolves inside Docker. Scripts running on your Mac need `localhost`:
> ```bash
> export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/migration_example
> ```

---

## Runbook — full walkthrough from clean state

### 0. Reset (if starting over)

```bash
docker compose down -v --remove-orphans
```

Destroys all containers and volumes. Start from step 1.

### 1. Start the database

```bash
cd data-ai/db-migration-example
docker compose up -d db
docker compose ps db   # wait until Status shows "healthy"
```

**Connecting with DBeaver or pgAdmin:**

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `migration_example` |
| Username | `postgres` |
| Password | `postgres` |

pgAdmin is also included in the stack — start it with `docker compose up -d pgadmin` and open `http://localhost:5050` (email: `admin@local.dev`, password: `admin`). Register a new server using the same connection details above, but set Host to `db` (the Docker-internal hostname).

### 2. Apply migrations (Expand phase)

```bash
./scripts/run_liquibase.sh update
```

Applies four changesets. The Contract changeset (`003`) is **skipped** — its precondition fails because `READ_MODE=legacy`.

### 3. Seed data

```bash
uv sync
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/migration_example
uv run python scripts/seed_data.py
```

Inserts 1,000 customers and 10,000 orders by default. ~5% are guest checkouts with no `billing_email`. Idempotent.

To seed a larger volume (e.g. for QA against RDS):

```bash
SEED_NUM_CUSTOMERS=50000 SEED_NUM_ORDERS=1000000 uv run python scripts/seed_data.py
```

### 4. Start the app — Legacy phase

`.env` defaults to `WRITE_MODE=legacy`. New orders write only to `orders.billing_email`.

```bash
docker compose up -d app
uv run python scripts/smoke_test.py   # → health ok
```

### 5. Enable dual-write

Edit `.env`: set `WRITE_MODE=dual`, then restart:

```bash
docker compose up -d app
```

New orders now write to both `orders.billing_email` and `order_contact_email`. Reads still come from `orders.billing_email`.

**Rollback:** Set `WRITE_MODE=legacy` and restart. Rows already in `order_contact_email` are harmless while `READ_MODE=legacy`.

### 6. Run the backfill worker

```bash
docker compose build worker   # rebuild if code changed since last run
docker compose up worker
```

The worker reads from `orders.billing_email`, copies rows into `order_contact_email` in batches of 1,000 (configurable via `BACKFILL_BATCH_SIZE`), and exits when done:

```json
{"last_order_id": 12500, "inserted": 1000, "elapsed_ms": 47.3}
...
backfill complete
```

**Rollback:** The backfill is safe to re-run (`ON CONFLICT DO NOTHING`). To undo:
```bash
docker exec db-migration-example-db-1 psql -U postgres -d migration_example \
  -c "TRUNCATE order_contact_email; UPDATE backfill_progress SET last_order_id=0, rows_processed=0;"
```

### 7. Verify readiness, then switch reads

```bash
uv run python scripts/verify_contract_ready.py
```

Before switching you'll see:
```
OK: all backfill rows are present in order_contact_email.
FAIL: READ_MODE is 'legacy', expected 'new'.
```

Switch reads to the new table (no redeploy — updates `app_runtime_config` in the DB):

```bash
uv run python scripts/switch_read_mode.py new
uv run python scripts/verify_contract_ready.py
# OK: all backfill rows are present in order_contact_email.
# OK: READ_MODE is 'new'.
# Contract phase is ready.
```

**Rollback:** Instant, no restart:
```bash
uv run python scripts/switch_read_mode.py legacy
```

### 8. Apply the Contract migration

```bash
./scripts/run_liquibase.sh update
```

The precondition now passes (`READ_MODE=new`) and `orders.billing_email` is dropped. **Irreversible** — take a DB snapshot before this step.

### 9. Stop dual-writing (cleanup)

`orders.billing_email` no longer exists. Edit `.env`: set `WRITE_MODE=new`, then restart:

```bash
docker compose up -d app
```

### 10. Run the test suite

Tests are phase-aware — they skip automatically based on the current `WRITE_MODE` and DB schema state.

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/migration_example
export BASE_URL=http://localhost:8000
uv sync --group test
uv run pytest tests/ -v
```

---

## Why `CREATE INDEX CONCURRENTLY`

A standard `CREATE INDEX` holds a `ShareLock` for the full build duration, blocking all writes. `CREATE INDEX CONCURRENTLY` builds in multiple passes with no long lock — writes continue uninterrupted. The trade-off: it takes longer and cannot run inside a transaction block, which is why the changeset sets `runInTransaction: false`.

For a new empty table the difference is academic. The pattern is shown here because it is the correct default for any index added to a live table.

---

## Upgrade-path test

The CI pipeline (`validate-and-test` job in `.github/workflows/deploy.yml`) is the canonical upgrade-path test. It resets to a clean PostgreSQL instance, applies all migrations, seeds data, starts the app, and runs the full test suite on every push to `main`.

---

## Production hardening

This example is for local rehearsal. See the [intentionally omitted](ARCHITECTURE.md#whats-intentionally-omitted) section in `ARCHITECTURE.md`.
