# Architecture

`aws-sdlc-containers` keeps the current platform deliberately small: one AWS
account/region, one ECS cluster, one PostgreSQL database, and one reference
workload that proves safe in-place rollout.

## Current architecture contract

- Base platform: split platform/app Terraform state, one VPC, one public
  WAF-protected API hostname, one ECS cluster, one long-running app service,
  PgBouncer in the app task, one PostgreSQL database, and one S3 data hub
  bucket.
- Application shape: one application system, one repository, and one shared
  database, deployed as multiple workload hosts. Those hosts may use different
  ECS services or task definitions without becoming accidental microservices.
- Reference workload: additive Liquibase migrations, in-place ECS deploys, runtime `WRITE_MODE` and `READ_MODE` switches, and one-off worker tasks all operate against that same cluster and database.
- Data workload: one scheduled ECS data export job writes the `order_contact_email` raw CSV and manifest objects to the S3 data hub bucket.
- Async workload: the app writes `order.created.v1` messages to a durable
  outbox. The order event runtime relays those rows through Dapr pub/sub, backed
  by AWS SNS/SQS on ECS, and records idempotent receipts for processed
  deliveries.
- Public-edge rule: public-facing ALBs must be associated with WAF.
- Extension rule: future observability stacks, extra operator controls, and workload-specific jobs should be added as extensions rather than folded into the core platform unless every workload would require them.

## Clean architecture package map

The repo is organized around dependency direction, not deployment shape:

- `packages/domain`: pure entities, value objects, and domain events.
- `packages/application`: use cases, ports, command/result objects, and outbox
  dispatch contracts.
- `packages/infrastructure`: SQLAlchemy repositories, Dapr pub/sub adapters,
  and storage/runtime integration.
- `apps/*`: workload hosts. They own settings, process lifecycle, HTTP routes,
  scheduler entrypoints, and concrete wiring.

Dependencies point inward:

```text
apps/*  -> packages/application -> packages/domain
apps/*  -> packages/infrastructure
packages/infrastructure -> packages/application + packages/domain
```

`packages/domain` and `packages/application` must not import FastAPI,
SQLAlchemy, boto3, Dapr adapter code, or app settings. The API can run as part
of a modular monolith today while preserving a clean extraction path for future
hosts because use cases speak ports and simple Python objects.

`packages/application/src/aws_sdlc_application/ports.py` defines the stable
application-facing contracts for synchronous order behavior:

```python
class OrderRepository(abc.ABC):
    def create_order(...) -> Order: ...
    def get_order(self, order_id: int) -> Order | None: ...
```

`packages/application/src/aws_sdlc_application/outbox.py` defines the outbox
relay contracts. `packages/infrastructure/src/aws_sdlc_infrastructure/db/`
implements the Postgres repositories and
`packages/infrastructure/src/aws_sdlc_infrastructure/dapr/pubsub.py` implements
the Dapr publisher adapter.

## Database capability ownership

The project keeps one Postgres database. Ownership is documented by capability
and table, not by pretending each workload owns a separate database:

| Capability | Tables | Current primary writers |
|---|---|---|
| Order write model | `customers`, `orders`, `order_contact_email` | API through `SQLAlchemyOrderRepository`; backfill writes historical contact rows |
| Runtime configuration | `app_runtime_config` | API admin endpoints through `SQLAlchemyConfigStore`; Liquibase seeds defaults |
| Outbox and event receipts | `outbox_messages`, `order_event_receipts`, `idempotency_keys` | API writes order/idempotency/outbox rows; order event host relays and records receipts |
| Migration/backfill control | `backfill_progress`, `DATABASECHANGELOG`, `DATABASECHANGELOGLOCK` | Liquibase and backfill worker |
| Export/data-hub outputs | S3 data hub objects under export prefixes | data export job |

This keeps operational reasoning simple: one schema migration history and one
transactional database, with separate compute hosts only where workload
lifecycle, scaling, or scheduling differs.

---

## Schema migration — expand/contract lifecycle

The migration moves `orders.billing_email` into a dedicated `order_contact_email` table using the manual expand → dual-write → backfill → switch → contract pattern.

The repository layer described above owns the runtime mode decision for each
request.

- `WRITE_MODE` (`legacy` → `dual` → `new`) controls which table(s) receive new writes. `legacy` is safe to deploy before `order_contact_email` exists. `dual` keeps both tables in sync during the backfill window so a `READ_MODE` rollback is always safe. `new` stops touching `orders.billing_email` and is the pre-condition for the contract phase.
- `READ_MODE` (`legacy` → `new`) controls which table serves reads. Decoupled from `WRITE_MODE` so the read cutover can be verified and rolled back independently.
- Both flags are stored in `app_runtime_config` and cached with a 5 s TTL — no redeploy needed to advance or roll back a phase.
- `ConfigStore` port + `SQLAlchemyConfigStore` keep the flag persistence behind an abstraction so the repository never imports HTTP or config concerns directly.
- `/admin/read-mode` and `/admin/write-mode` expose the switches as HTTP endpoints for the runbook and CI `curl` commands.
- `require_phase` markers in the test suite gate each test to the phases where its invariant holds, detected from the live `app_runtime_config` rows at session start.

### Relationship with Liquibase

Liquibase owns the migration history (`DATABASECHANGELOG`) and runs all DDL: bootstrapping tables, creating `app_runtime_config`, seeding config rows, and the `order_contact_email` table creation.

Liquibase connects directly to Postgres (not via PgBouncer) — DDL statements require a persistent session connection.

---

## PgBouncer — connection pooling

PgBouncer runs as a sidecar in every environment:

- **Local / Docker Compose**: `pgbouncer` service, app connects to `pgbouncer:5432` (port 6432 on the host).
- **ECS Fargate**: `pgbouncer` container in the same task definition as `app`. Both share the task's network namespace — the app connects to `localhost:5432`.

**Why transaction mode**: server connections are returned to the pool after each transaction. A request that takes 10ms holds a server connection for 10ms, not for the lifetime of the HTTP connection. This allows many app connections to share a small RDS pool.

**Why `NullPool` in SQLAlchemy**: stacking SQLAlchemy's own pool on top of PgBouncer's pool would hold server connections idle inside SQLAlchemy between requests, defeating PgBouncer's multiplexing. `NullPool` means SQLAlchemy opens and closes a pgbouncer client connection per request. PgBouncer maps that to a pooled server connection for the transaction duration.

**Pool sizing**: `default_pool_size=20` server connections to RDS. RDS `db.t4g.small` has `max_connections ≈ 97`. 20 server connections leaves headroom for superuser, monitoring, and Liquibase connections. Adjust `pgbouncer_pool_size` in `stack.tfvars` if connection wait times appear in pgbouncer logs.

**Liquibase bypasses PgBouncer**: it uses DDL that requires a persistent session. It connects directly to the RDS endpoint, not via PgBouncer.

---

## Test design

Tests connect to the live DB via PgBouncer (same `DATABASE_URL` as the app) and to the running app via HTTP. `conftest.py` detects the current migration phase from `app_runtime_config` at session start and uses it to skip tests whose invariants don't hold in the current phase — `require_phase("dual", "switch")` skips in `legacy` and `post_contract`, for example. This means the same test suite runs at every phase of the runbook; only the relevant subset executes.

`committed_db_session` cleans up test rows by watermark after each test. Teardown is unconditional — a failing assertion cannot leave the DB in a state that breaks subsequent tests.

---

## Async order events

The first async workflow is deliberately narrow: after an order is created, the
app writes an `order.created.v1` message to `outbox_messages` in the same
database transaction as the order. The `order-event-consumer` runtime runs as a
small Dapr-enabled FastAPI service. Its background relay claims pending outbox
rows and publishes CloudEvents to the local Dapr sidecar; Dapr uses the
`order-events-pubsub` component to deliver through AWS SNS/SQS on ECS. Dapr then
calls the runtime's subscription endpoint, which records deliveries into
`order_event_receipts`.

The event contract uses `order.created.v1:<order_id>` for both `event_id` and
`idempotency_key`. Dapr receives CloudEvents with the existing order payload in
the `data` field, and the AWS SNS/SQS component runs in FIFO mode with
single-concurrency delivery for this topic.

The outbox relay claims rows with `FOR UPDATE SKIP LOCKED`, marks successful
publishes as `published`, and leaves failed publishes retryable with backoff.
The consumer deduplicates by `event_id`, increments duplicate counts for repeat
deliveries, and records late/stale events as `ignored_stale` when a newer event
for the same aggregate has already been processed.

The subscriber queue has a DLQ and a CloudWatch alarm for visible DLQ messages.
The runbook is `docs/runbooks/order-event-queue-failure.md`.

### Dapr resiliency policy

The order event sidecar loads a scoped Dapr resiliency spec from the same
resources path as the `order-events-pubsub` component. The policy is intentionally
small and bounded:

- 10 s timeout for pub/sub component operations.
- 2 constant retries with a 1 s interval.
- circuit breaker after more than 5 consecutive failures, reopening after 30 s.
- both outbound publish calls and inbound subscription callbacks use the same
  policy.

This gives the application layer a portable failure-handling foundation without
turning a single event flow into a platform framework. The durable database
outbox and SQS DLQ remain the long-lived recovery mechanisms; Dapr handles the
short transient edge around broker calls and callback delivery.

### Broader Dapr direction

Dapr is the chosen application-layer foundation because it makes future
complexity manageable: transport, resiliency, service invocation, workflows, and
runtime integration can grow behind consistent building blocks. That does not
mean every building block is added up front. Inside the current modular
monolith, direct Python calls, explicit ports, and the existing Postgres
repository remain simpler than routing everything through Dapr.

Postgres can still participate in Dapr when the boundary is Dapr-owned runtime
state, not core OLTP repository behavior. Dapr supports PostgreSQL as a state
store component and as a PostgreSQL output binding; either can be useful later
for workflow checkpoints, operational job state, or narrow integration tasks.
Those components should use separate tables or schemas from the order write
model and outbox tables so the application database remains easy to reason
about.

Analytics workloads should follow the same host/package rule. A DuckDB, dbt, or
data-load job can live as a separate workload host when it has its own schedule,
resources, or deploy lifecycle, while reusable orchestration belongs in
`packages/application` and concrete adapters belong in `packages/infrastructure`.
Postgres remains the transactional source of truth; analytics outputs should be
owned as data products in S3 prefixes, dedicated analytics tables/schemas, or a
separate store when query shape and retention justify it.

## Request idempotency

`POST /orders` accepts an optional `Idempotency-Key` header. When present, the
API hashes the stable request body fields and stores the in-flight request in
`idempotency_keys`.

- Same key and same request: returns the stored original response.
- Same key and different request: returns `409`.
- Concurrent same-key requests: one request creates the order; retrying callers
  wait briefly for the stored response and receive the same order response.

Clients that omit `Idempotency-Key` keep the original behavior: every successful
`POST /orders` creates a new order.

---

## Split-root stack strategy

The project uses one long-lived AWS stack split into platform and app
Terraform roots rather than separate dev/prod stacks or ephemeral preview
environments. The rationale:

- The safe rollout mechanism already exists inside the workload: additive Liquibase changes, independent task definitions, runtime read/write switches, and a checkpointed worker.
- Separate stacks would add naming, state, workflow, and documentation overhead without improving the migration behavior being demonstrated here.
- Platform resources such as VPC networking and GitHub OIDC have a different
  lifecycle from app resources such as RDS, ECS, ALB, workload jobs, and
  observability.
- The project stays easier to understand when the interesting part is the in-place migration sequence, not environment promotion choreography.

**Reset procedure**:

```bash
terraform -chdir=infra/app init -backend-config="key=aws-sdlc-containers/app.tfstate" -reconfigure
terraform -chdir=infra/app destroy -var-file=stack.tfvars
terraform -chdir=infra/app apply   -var-file=stack.tfvars
```

Then re-run the full runbook from step 2 against the fresh RDS instance.

---

## What's Intentionally Omitted

These items are intentionally deferred to later phases. They are hardening or extension work, not part of the current base platform contract.

- Backfill throttling based on replication lag or primary CPU load
- Rolling deploy coordination — during the dual-write window, old and new app versions run simultaneously; both write to `orders.billing_email` and `order_contact_email`, but this is not explicitly tested under concurrent load
- PgBouncer pool exhaustion handling — `max_client_conn=200` is a hard limit; requests beyond that are rejected. A circuit breaker or queue in front of the app would be needed at high scale
- `CREATE INDEX CONCURRENTLY` failure detection (check `pg_indexes` for `INVALID`)
- Secrets management (`DATABASE_URL` in `.env` is local-only; ECS injects credentials via Secrets Manager)
- DB snapshot before the contract phase (drop column)
- Pub/sub cache invalidation for any remaining runtime config flags across multiple instances

---

## Request security — TLS and authentication

### Request flow

```
caller
  │  HTTPS (TLS 1.2+, ACM-managed cert)
  ▼
ALB (public subnet)
  │  checks Authorization: Bearer <token>
  │  ✗ missing/wrong → 401 fixed-response (app never sees the request)
  │  ✓ match → forward
  ▼
app container (private subnet, port 8000, plain HTTP)
  │
  ▼
pgbouncer → RDS (intra subnet, no internet route)
```

TLS terminates at the ALB. Traffic from the ALB to the app container is plain HTTP inside the VPC — the private subnet and security group (inbound from ALB SG only) are the network boundary.

### Why fixed-token auth at the ALB, not in the app

The ALB listener rule rejects unauthenticated requests before they reach the app. This means:

- No auth middleware in the app — the HTTP layer stays focused on domain concerns.
- The 401 is returned by AWS infrastructure, not application code — no risk of an auth bypass from an unhandled exception in the app.
- The token is read from Secrets Manager at `terraform apply` time and embedded in the listener rule condition. It is never stored in the app's environment or logs.

The trade-off: the token is a shared secret with no per-caller identity. Suitable for a demo or internal tool; replace with Cognito/OIDC on the ALB for multi-caller identity.

### Why an ACM-managed certificate

The lean stack still uses a real DNS name: `api.<root_domain>`. Because the domain lives in Route 53, Terraform can request an ACM certificate, create the validation records automatically, and attach the certificate to the ALB without any out-of-band certificate handling.

### How the certificate is wired

Terraform creates:

1. An ACM certificate for `api.<root_domain>`.
2. The Route 53 validation records ACM requires.
3. The validation resource that waits for issuance.
4. The HTTPS listener using the validated ACM certificate.

That keeps TLS fully declarative and removes the need for account-specific helper files or manual certificate import steps.

### ALB security group

Port 443 is open to `0.0.0.0/0` — the fixed-token header check is the access control layer. There is no HTTP listener or redirect path; callers use HTTPS directly. The app SG allows inbound on port 8000 from the ALB SG only, so direct access to the app container from outside the VPC is not possible.

### ECS service security group — pre-create to break circular dependency

The `terraform-aws-modules/ecs` module creates its own security group for the service when `security_group_ingress_rules` / `security_group_egress_rules` are defined. This creates a circular dependency when RDS also needs to reference the app SG:

```
aws_security_group.rds → module.ecs SG → module.ecs → module.rds endpoint → module.rds → aws_security_group.rds
```

The pattern to break this: pre-create `aws_security_group.app` before either module, pass it to the ECS module via `create_security_group = false` + `security_group_ids`, and reference it from the RDS SG ingress rule. Both modules can then reference the same SG ID without a cycle. This is the standard pattern when two modules need to reference each other's security groups.

### Shared ECS task execution role — pre-create to avoid null module outputs

The `terraform-aws-modules/ecs` module creates its own execution role internally. The liquibase and worker task definitions need the same role (with `GetSecretValue` on the RDS secret), but they are defined as standalone `aws_ecs_task_definition` resources outside the module. Referencing `module.ecs.services["app"].task_exec_iam_role_arn` from those resources would produce a null value during the same plan that creates the ECS service — Terraform cannot resolve a module output that doesn't exist yet.

The fix: pre-create `aws_iam_role.task_exec` (plus its policy attachment and inline policies) before the ECS module, then pass it to the module via `create_task_exec_iam_role = false` + `task_exec_iam_role_arn`. All three task definitions (app, liquibase, worker) reference the same role ARN without any module output dependency.

### Liquibase and worker as standalone task definitions

The ECS module's `services` block is designed for long-running services: ALB integration, desired count, health checks, service scheduler. Liquibase and the worker are one-off Fargate tasks — no listener, no desired count, no service. The module has no concept of a one-off task. Native `aws_ecs_task_definition` resources are the correct tool; the CI pipeline runs them via `aws ecs run-task`.

### CloudWatch log groups for liquibase and worker

The ECS module auto-creates log groups only for containers defined inside its `services` block. Because liquibase and worker containers are defined in standalone task definitions, the module never sees them. Their log groups must be created explicitly — the `awslogs` log driver fails at task startup if the group does not already exist.

### SSM exec policy attached outside the module

`aws_iam_role_policy.task_ssm_exec` attaches SSM permissions to the app task's runtime role (`tasks_iam_role`). That role is created by the ECS module, so its name is only available as `module.ecs.services["app"].tasks_iam_role_name` — a post-apply output. The policy cannot be passed into the module; it must be attached after the module creates the role. This is a standard post-module attachment pattern for permissions that depend on a module-managed role.

### ECS Exec and readonlyRootFilesystem

The `terraform-aws-modules/ecs` module defaults `readonlyRootFilesystem = true` for all containers. The SSM managed agent (used by `enable_execute_command`) requires write access to `/var/lib/amazon` and `/var/log/amazon` at startup — it does not support readonly root on Fargate 1.4, even with tmpfs mounts covering `/tmp`. The agent starts but immediately stops with no error reason.

The fix is `readonlyRootFilesystem = false` on any container that needs ECS Exec. The meaningful security boundary in this architecture is IAM + private subnet + security groups, not filesystem immutability. If readonly root is a hard requirement, the only supported workaround requires modifying the Dockerfile to declare volumes for those two paths and defining matching bind-mount volumes in the task definition — see the [upstream issue](https://github.com/aws/containers-roadmap/issues/1359).

### SSM port forwarding target format

`aws ssm start-session` with `AWS-StartPortForwardingSessionToRemoteHost` requires the full three-part target for ECS Fargate tasks:

```
ecs:<cluster-name>_<task-id>_<container-runtime-id>
```

The runtime ID is distinct from the task ID and is only available after the task is fully running. Query it via:

```bash
aws ecs describe-tasks \
  --cluster <cluster> --tasks <task-arn> \
  --query 'tasks[0].containers[?name==`app`].runtimeId' \
  --output text
```

The `make db-tunnel` target fetches this automatically.

### Log noise on ECS

Two sources of high-frequency log noise in a typical ECS + ALB setup:

- ALB health checks — fire every `interval` seconds from each AZ plus the ECS container health check. Filtered at the Uvicorn access logger level in `apps/api/src/aws_sdlc_api/main.py` using a `logging.Filter` subclass. Non-200 responses on `/health` still pass through.
- PgBouncer stats logs — fire every `stats_period` seconds (default 60s) regardless of traffic. Controlled via the `STATS_PERIOD` environment variable. Set to 3600 (hourly) — low enough to preserve pool pressure signal, high enough to eliminate per-minute noise. Set to 0 to disable entirely.

---

## Cost estimate

All prices are us-east-1 on-demand as a reference baseline. eu-central-1 (the configured region) runs ~10% higher. Figures are per-month unless noted.

### Lean AWS stack

| Resource | Config | $/mo (approx) |
|---|---|---|
| ECS Fargate — app + pgbouncer | 1 task × 0.5 vCPU / 1 GiB, ~730 h | ~$15 |
| RDS Postgres | db.t4g.small, Single-AZ, 20 GB gp3 | ~$25 |
| ALB | 1 ALB + ~0 LCU at idle | ~$17 |
| NAT Gateway | 1 shared × $0.045/h + data | ~$33 |
| ECR | 5 repos, ~10 images each, <1 GB total | ~$1 |
| S3 data hub | Raw/manifest exports, low volume | <$1 |
| CloudWatch Logs | app + pgbouncer, 14–30 day retention, low volume | ~$2 |
| Secrets Manager | 1 RDS secret + 1 API token | ~$1 |
| **Estimated total** | | **~$94/mo** |

### Notes

- NAT Gateway dominates non-compute cost. If ECR pulls are the main egress driver, [VPC endpoints for ECR and Secrets Manager](https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html) can cut NAT data charges significantly.
- RDS Performance Insights (7-day retention) is free. Extending to 731 days adds ~$20/mo per instance.
- Worker, Liquibase, and data export tasks are short Fargate runs (seconds to minutes) — cost is negligible (<$0.01/run) and not included above.
- CloudWatch Container Insights (optional, not currently enabled) adds ~$0.35/node/hour if turned on.
- These are idle/low-traffic baselines. ALB LCU and NAT data charges scale with actual request volume.
