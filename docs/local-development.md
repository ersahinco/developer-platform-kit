# Local Development

This page is the local development runbook for the current repository shape.
Deployable workloads live under `apps/`: the API in `apps/api/`, the backfill
worker in `apps/backfill-worker/`, and the local data export job in
`apps/data-export-job/`.

## Prerequisites

- Docker Desktop
- Python 3.14+
- `uv`
- Optional infra and quality tools: Terraform, tflint, checkov, pre-commit, AWS CLI, Session Manager plugin, actionlint, lychee, hadolint, and gitleaks

The recommended way to keep a personal machine aligned with the project
toolchain is to open the repository in its dev container. It installs Python
3.14, `uv`, Docker CLI/Compose access, Terraform 1.15.0, TFLint, Checkov,
pre-commit, AWS CLI, actionlint, lychee, hadolint, and gitleaks.

In VS Code, run **Dev Containers: Reopen in Container**. On first create, the
container runs:

```bash
uv sync --all-packages --group dev --group test
pre-commit install --hook-type pre-commit --hook-type pre-push
```

Inside the dev container, commands that connect back to local Docker Compose
services use `host.docker.internal` defaults. Outside the dev container, keep
using `localhost` as shown below.

## Environment Variables

| Variable | Effect |
|---|---|
| `DATABASE_URL` | App and test connection string. Locally this usually points to PgBouncer on `localhost:6432`. |
| `BACKFILL_DATABASE_URL` | Worker connection string. Locally this points directly to Postgres on `localhost:5432`. |
| `DATA_EXPORT_DATABASE_URL` | Data export job connection string. Locally this points directly to Postgres on `localhost:5432`. |
| `DATA_EXPORT_OUTPUT_DIR` | Data export output directory. Docker Compose defaults to `/exports` backed by the `data_exports` volume. |
| `SEED_NUM_CUSTOMERS` | Number of customers to seed. Default: 1000. |
| `SEED_NUM_ORDERS` | Number of orders to seed. Default: 10000. |

Copy the example env file if you want to override defaults:

```bash
cp .env.example .env
```

Docker Compose has safe local defaults for the app, database, and observability
ports. Host commands should use `localhost`. Containers should use Docker
service names such as `pgbouncer` and `db`.

## Full Local Walkthrough

### 0. Reset from a previous run

```bash
docker compose down -v --remove-orphans
```

### 1. Start Postgres and PgBouncer

```bash
docker compose up -d db pgbouncer
docker compose ps
```

Direct Postgres connection from a host tool:

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `aws_sdlc_containers` |
| Username | `postgres` |
| Password | `postgres` |

PgBouncer connection from a host tool:

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `6432` |
| Database | `aws_sdlc_containers` |
| Username | `postgres` |
| Password | `postgres` |

Optional pgAdmin:

```bash
docker compose --profile tools up -d pgadmin
```

Open `http://localhost:5050` with email `admin@local.dev` and password
`admin`. Use `db` as the host when registering the server inside pgAdmin.

### 2. Apply Liquibase migrations

```bash
docker compose --profile migration -f docker-compose.yml run --rm liquibase update
```

This creates the bootstrap schema, the runtime config table, and the expanded
`order_contact_email` table.

### 3. Seed data

```bash
uv sync --all-packages
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aws_sdlc_containers
uv run python scripts/seed_data.py
```

The seed command is idempotent. By default it inserts 1000 customers and 10000
orders.

### 4. Start the app

```bash
docker compose build app
docker compose up -d app
curl --fail --show-error http://localhost:8000/health
```

### 5. Advance writes to dual mode

After `order_contact_email` exists, tell the app to write to both tables:

```bash
export BASE_URL=http://localhost:8000
curl --fail --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{"mode":"dual"}' \
  "$BASE_URL/admin/write-mode"
```

The app updates the DB-backed runtime config through the admin API and drops
its local cache immediately. Other instances pick up the change within the
configured TTL window.

### 6. Run the backfill worker

```bash
docker compose build worker
docker compose up worker
```

The worker reads from `orders.billing_email`, writes to `order_contact_email`,
and exits when complete. It is safe to rerun because inserts are idempotent and
the checkpoint advances only after a successful batch commit.

For a throttled repair or replay, bound a run to a small number of committed
batches:

```bash
docker compose run --rm -e BACKFILL_MAX_BATCHES=1 worker
```

When the limit is reached, the worker exits successfully after logging a
`backfill_paused` JSON event. Re-run the same command to continue from the
checkpoint.

### 7. Switch reads to the new table

```bash
export BASE_URL=http://localhost:8000
curl --fail --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{"mode":"new"}' \
  "$BASE_URL/admin/read-mode"
```

Run the full test suite:

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:6432/aws_sdlc_containers
uv sync --all-packages --group test
uv run pytest tests/ -v
```

The tests detect the current migration phase from `app_runtime_config` and skip
phase-specific assertions that do not apply.

### 8. Advance writes to new mode

```bash
curl --fail --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{"mode":"new"}' \
  "$BASE_URL/admin/write-mode"
```

This stops writing to `orders.billing_email` and prepares for the contract
phase.

### 9. Apply the contract migration

```bash
docker compose --profile migration -f docker-compose.yml run --rm liquibase update
```

The contract migration drops `orders.billing_email`. This is irreversible in a
live environment, so take a database snapshot before this step on AWS.

## Useful Make Targets

```bash
make help
make dev
make observability
make data-export
make migrate
make seed
make test
make lint
make fmt
```

## Optional Observability

After the app is running, start the local observability stack:

```bash
make observability
```

Then open:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- App metrics: `http://localhost:8000/metrics`

Grafana defaults to `admin` / `admin`. See `observability.md` for the local
stack design and acceptance criteria.

## Optional Data Export

After migrations have created `order_contact_email`, run the local data export
job:

```bash
make data-export
```

It writes `raw/order_contact_email/dt=<date>/<run-id>.csv` and a matching
success manifest into the `data_exports` Docker volume. In AWS, the scheduled
ECS data export job uploads those same relative keys to the data hub S3 bucket.

AWS operator targets are documented in `deployment.md`.
