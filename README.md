# db-migration-example

A fully-runnable local example of zero-downtime schema migration using the **expand/contract** pattern and **PgBouncer** for connection pooling across all environments.

The concrete migration: moving `orders.billing_email` into a dedicated `order_contact_email` table — without downtime, without locking the table, without a flag day.

---

## What this demonstrates

| Concern | Mechanism | Key files |
|---|---|---|
| Schema bootstrap | Liquibase changesets | `db/changelog/000-bootstrap.yaml`, `002-app-runtime-config.yaml` |
| Column migration | Expand/contract (dual-write + backfill + switch) | `db/changelog/`, `worker/src/backfill.py` |
| Connection pooling | PgBouncer (transaction mode) | `docker-compose.yml`, `db/pgbouncer/pgbouncer.ini`, `infra/main.tf` |
| Zero-downtime deploy | ECS rolling update + WRITE_MODE/READ_MODE flags | `infra/main.tf`, `.github/workflows/deploy.yml` |

---

## How it works

The migration follows the **expand → dual-write → backfill → switch → contract** pattern:

1. Expand — Liquibase creates `order_contact_email`. `orders.billing_email` still exists.
2. Dual-write — advance `WRITE_MODE=dual` via the admin API. The app writes to both tables.
3. Backfill — the worker copies historical rows from `orders.billing_email` into `order_contact_email`.
4. Switch — advance `READ_MODE=new`. The app reads from `order_contact_email`.
5. Contract — advance `WRITE_MODE=new`, then drop `orders.billing_email` via a Liquibase changeset.

**PgBouncer** sits between the app and Postgres in every environment. The app's `DATABASE_URL` points to PgBouncer, not Postgres directly. PgBouncer runs in transaction mode — server connections are returned to the pool after each transaction, multiplexing many app connections onto a small RDS pool. SQLAlchemy uses `NullPool` so it does not stack its own pool on top of PgBouncer's.

Liquibase connects directly to Postgres (not via PgBouncer) — DDL statements require a persistent session connection.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design rationale.

---

## Prerequisites

- Docker Desktop — [install](https://docs.docker.com/desktop/install/mac-install/)
- Python 3.12+ — `brew install python@3.12`
- `uv` — `brew install uv`

---

## Project layout

```
db-migration-example/
├── app/src/
│   ├── config.py                 # pydantic-settings: DATABASE_URL
│   ├── db.py                     # SQLAlchemy engine (NullPool — pgbouncer owns pooling)
│   ├── domain/
│   │   ├── order.py              # Order entity — pure Python
│   │   └── ports.py              # Abstract interface: OrderRepository
│   └── adapters/
│       ├── api/main.py           # FastAPI routes
│       └── db/repository.py      # Writes to + reads from order_contact_email
├── db/
│   ├── changelog/                # Liquibase: bootstrap + app_runtime_config
│   ├── pgbouncer/pgbouncer.ini   # PgBouncer config (used as reference; Docker uses env vars)
│   └── sql/bootstrap.sql         # Postgres init: pg_stat_statements extension
├── scripts/                      # seed, smoke test
├── tests/                        # pytest integration tests
├── .env.example                  # All env vars with safe local defaults
└── docker-compose.yml
```

---

## Environment variables

| Variable | Effect |
|---|---|
| `DATABASE_URL` | App/test connection string — points to PgBouncer (`localhost:6432` on the host, `pgbouncer:5432` inside Docker) |
| `BACKFILL_DATABASE_URL` | Worker connection string — points directly to Postgres, bypassing PgBouncer (`localhost:5432` on the host, `db:5432` inside Docker) |
| `SEED_NUM_CUSTOMERS` | Number of customers to seed (default: 1,000) |
| `SEED_NUM_ORDERS` | Number of orders to seed (default: 10,000) |

Copy the example env file once:

```bash
cp .env.example .env
```

> **Host vs container hostnames** — `.env` uses Docker service names (`pgbouncer`, `db`). Anything running on your Mac (scripts, tests) must use `localhost` instead:
> ```bash
> export DATABASE_URL=postgresql://postgres:postgres@localhost:6432/migration_example
> ```
> The test suite rewrites `BACKFILL_DATABASE_URL` automatically — `conftest.py` loads `.env` at startup (putting the Docker-internal `db:5432` URL into the environment), and `test_backfill.py` unconditionally overwrites it with a `localhost:5432` URL derived from `DATABASE_URL` before spawning the worker subprocess.

---

## Runbook — full walkthrough from clean state

### 0. Reset (if starting over)

```bash
docker compose down -v --remove-orphans
```

### 1. Start the database and PgBouncer

```bash
docker compose up -d db pgbouncer
docker compose ps   # wait until db is healthy
```

**Connecting with DBeaver or pgAdmin (direct Postgres):**

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `migration_example` |
| Username | `postgres` |
| Password | `postgres` |

**Connecting via PgBouncer** (mirrors what the app sees):

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `6432` |

pgAdmin is available as an optional dev tool:
```bash
docker compose --profile tools up -d pgadmin
```
Open `http://localhost:5050` (email: `admin@local.dev`, password: `admin`). Use `db` as the host when registering the server inside Docker.

### 2. Apply Liquibase migrations

```bash
./scripts/run_liquibase.sh update
```

Creates `customers` and `orders` tables (bootstrap), `order_contact_email` (expand), and `app_runtime_config` (runtime config).

### 3. Seed data

```bash
uv sync
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/migration_example
uv run python scripts/seed_data.py
```

Inserts 1,000 customers and 10,000 orders. ~5% are guest checkouts with no `billing_email`. Idempotent.

### 4. Start the app

```bash
docker compose build app
docker compose up -d app
uv run python scripts/smoke_test.py   # → health ok
```

### 4a. Advance WRITE_MODE to dual

Now that `order_contact_email` exists, tell the app to write to both tables. This is done via the admin API — not a direct DB write — so the in-process TTL cache is invalidated immediately across all instances:

```bash
export BASE_URL=http://localhost:8000
uv run python scripts/set_runtime_config.py write-mode dual
```

### 5. Run the backfill worker

```bash
docker compose build worker
docker compose up worker
```

The worker reads from `orders.billing_email`, copies rows into `order_contact_email` in batches, and exits when done:

```json
{"last_order_id": 5000, "inserted": 1000, "elapsed_ms": 42.1}
...
backfill complete
```

Safe to re-run (`ON CONFLICT DO NOTHING`). Crash-safe — the checkpoint cursor advances only on successful batch commit.

### 6. Switch READ_MODE and run the test suite

Switch reads to the new table now that the backfill is complete:

```bash
export BASE_URL=http://localhost:8000
uv run python scripts/set_runtime_config.py read-mode new
```

Then run the full suite — phase detection will see `WRITE_MODE=dual`, `READ_MODE=new` → `switch` phase, which exercises the maximum number of tests:

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:6432/migration_example
uv sync --group test
uv run pytest tests/ -v
```

### 7. Advance WRITE_MODE to new (pre-contract)

Once reads are verified on the new table, stop writing to `orders.billing_email`:

```bash
uv run python scripts/set_runtime_config.py write-mode new
```

### 8. Apply the Contract migration (drop column)

Once all app instances are running the new code and `WRITE_MODE=new`, apply the contract changeset via Liquibase:

```bash
./scripts/run_liquibase.sh update
```

This drops `orders.billing_email`. **Irreversible** — take a DB snapshot before this step in production.

---

## Why `CREATE INDEX CONCURRENTLY`

A standard `CREATE INDEX` holds a `ShareLock` for the full build duration, blocking all writes. `CREATE INDEX CONCURRENTLY` builds in multiple passes with no long lock — writes continue uninterrupted. The trade-off: it takes longer and cannot run inside a transaction block.

---

## Why PgBouncer in transaction mode

SQLAlchemy uses `NullPool` — it does not maintain its own idle connections. Each request opens a pgbouncer client connection, which pgbouncer maps to a pooled server connection for the duration of the transaction.

---

## Upgrade-path test

The CI pipeline (`validate-and-test` job in `.github/workflows/deploy.yml`) resets to a clean PostgreSQL instance, runs Liquibase, seeds data, starts the app, and runs the full test suite on every push to `main`.

The `build-and-push` job runs `trivy image --severity CRITICAL` on the app image before pushing to ECR.

---

## Production hardening

This example is for local rehearsal. See the [intentionally omitted](ARCHITECTURE.md#whats-intentionally-omitted) section in `ARCHITECTURE.md`.
