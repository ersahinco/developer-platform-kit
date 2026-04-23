# Architecture

`aws-sdlc-containers` uses this workload to exercise the platform patterns that will later expand into observability, network security, and broader SDLC automation.

## Why hexagonal architecture?

The HTTP layer (`main.py`) never touches SQL directly. It calls abstract ports (`OrderRepository`), and the concrete implementation in `repository.py` handles all storage concerns. This boundary is what makes the migration transparent to the HTTP layer — the route handler for `GET /orders/{id}` is unchanged whether `billing_email` lives in `orders` or `order_contact_email`.

`ports.py` defines what the domain needs:

```python
class OrderRepository(abc.ABC):
    def create_order(...) -> Order: ...
    def get_order(self, order_id: int) -> Order | None: ...
```

`repository.py` reads `WRITE_MODE` and `READ_MODE` from `app_runtime_config` (TTL-cached, 5 s) to decide which table(s) to write to and read from.

---

## Layer map

```
adapters/api/        — HTTP boundary (FastAPI routes, Pydantic schemas)
                           ↓ calls ports only, no SQLAlchemy imports
domain/              — Order entity, abstract ports (pure Python)
                           ↓ implemented by
adapters/db/         — SQLAlchemy models, repository (all SQL lives here)
db.py                — engine (NullPool), session factory, get_db()
```

---

## Schema migration — expand/contract lifecycle

The migration moves `orders.billing_email` into a dedicated `order_contact_email` table using the manual expand → dual-write → backfill → switch → contract pattern.

`repository.py` reads `WRITE_MODE` and `READ_MODE` from `app_runtime_config` (TTL-cached, 5 s) to decide which table(s) to write to and read from.

- `WRITE_MODE` (`legacy` → `dual` → `new`) controls which table(s) receive new writes. `legacy` is safe to deploy before `order_contact_email` exists. `dual` keeps both tables in sync during the backfill window so a `READ_MODE` rollback is always safe. `new` stops touching `orders.billing_email` and is the pre-condition for the contract phase.
- `READ_MODE` (`legacy` → `new`) controls which table serves reads. Decoupled from `WRITE_MODE` so the read cutover can be verified and rolled back independently.
- Both flags are stored in `app_runtime_config` and cached with a 5 s TTL — no redeploy needed to advance or roll back a phase.
- `ConfigStore` port + `SQLAlchemyConfigStore` keep the flag persistence behind an abstraction so `repository.py` never imports HTTP or config concerns directly.
- `/admin/read-mode` and `/admin/write-mode` expose the switches as HTTP endpoints for the runbook and `scripts/set_runtime_config.py`.
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

## Single stack strategy

The project uses one long-lived AWS stack rather than separate dev/prod stacks or ephemeral preview environments. The rationale:

- The safe rollout mechanism already exists inside the workload: additive Liquibase changes, independent task definitions, runtime read/write switches, and a checkpointed worker.
- Separate stacks would add naming, state, workflow, and documentation overhead without improving the migration behavior being demonstrated here.
- The project stays easier to understand when the interesting part is the in-place migration sequence, not environment promotion choreography.

**Reset procedure**:

```bash
cd infra
terraform init -backend-config="key=aws-sdlc-containers/stack.tfstate" -reconfigure
terraform destroy -var-file=stack.tfvars
terraform apply   -var-file=stack.tfvars
```

Then re-run the full runbook from step 2 against the fresh RDS instance.

---

## What's intentionally omitted

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

Port 443 open to `0.0.0.0/0` — the fixed-token header check is the access control layer. Port 80 open only to redirect to HTTPS. The app SG allows inbound on port 8000 from the ALB SG only — direct access to the app container from outside the VPC is not possible.

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

- ALB health checks — fire every `interval` seconds from each AZ plus the ECS container health check. Filtered at the Uvicorn access logger level in `adapters/api/main.py` using a `logging.Filter` subclass. Non-200 responses on `/health` still pass through.
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
| ECR | 4 repos, ~10 images each, <1 GB total | ~$1 |
| CloudWatch Logs | app + pgbouncer, 14–30 day retention, low volume | ~$2 |
| Secrets Manager | 1 RDS secret + 1 API token | ~$1 |
| **Estimated total** | | **~$94/mo** |

### Notes

- NAT Gateway dominates non-compute cost. If ECR pulls are the main egress driver, [VPC endpoints for ECR and Secrets Manager](https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html) can cut NAT data charges significantly.
- RDS Performance Insights (7-day retention) is free. Extending to 731 days adds ~$20/mo per instance.
- Worker and Liquibase tasks are one-off Fargate runs (seconds to minutes per migration cycle) — cost is negligible (<$0.01/run) and not included above.
- CloudWatch Container Insights (optional, not currently enabled) adds ~$0.35/node/hour if turned on.
- These are idle/low-traffic baselines. ALB LCU and NAT data charges scale with actual request volume.
