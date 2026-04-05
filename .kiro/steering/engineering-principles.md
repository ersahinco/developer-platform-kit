# Engineering Principles

These principles apply to all code, tests, scripts, configuration, infrastructure, and documentation in this project.

---

## Lean development

- Every file, class, function, and dependency must earn its place. If removing it does not break anything meaningful, remove it.
- No speculative abstractions. Build for the problem in front of you, not the one you imagine might arrive.
- No wrapper code that only delegates. If a function does nothing but call another function with the same arguments, it is noise.
- Dependencies are liabilities. Add a library only when the alternative is reimplementing something non-trivial. Prefer stdlib and already-present deps.
- Configuration surfaces (env vars, flags, feature toggles) must be the minimum needed to control the behaviour being demonstrated. Each variable must have a documented effect and a safe default.

---

## Maintainability

- Code is read far more than it is written. Optimise for the reader.
- Each module has one reason to change. HTTP concerns stay in `adapters/api`, SQL concerns stay in `adapters/db`, domain logic stays in `domain/`. Nothing crosses those boundaries without a port.
- Tests are the first consumer of the code. If a test is hard to write, the design is the problem, not the test.
- Fixtures and helpers shared across tests live in `conftest.py`. Test files contain only assertions.
- Use well-known libraries for well-known problems: `pydantic-settings` for config, `python-dotenv` for `.env` loading, `testcontainers` for hermetic DB tests. Do not hand-roll what a maintained library already does correctly.
- Migration changesets are append-only. Never edit a changeset that has been applied to any environment.

---

## Clarity

- Names describe intent, not implementation. `get_read_mode` is clear. `fetch_val_from_cfg_tbl` is not.
- Comments explain *why*, not *what*. If the code needs a comment to explain what it does, rewrite the code.
- Every non-obvious decision gets a one-line rationale inline: why `CREATE INDEX CONCURRENTLY`, why `ON CONFLICT DO NOTHING`, why `override=False` in `load_dotenv`.
- Runbook steps map 1-to-1 with migration phases. A reader following the README must never need to infer a step.
- Test names are full sentences describing the invariant being checked, not the mechanism.

---

## Real-world patterns over workarounds

- Solve problems with the established pattern for that class of problem:
  - Schema migrations: expand → dual-write → backfill → switch → contract. Never a flag day.
  - For teams wanting a higher-level abstraction, [pgroll](https://github.com/xataio/pgroll) is a viable alternative — it manages the expand/contract lifecycle automatically and supports instant rollback. Use it when the manual pattern becomes operationally expensive.
  - Hermetic migration tests: Testcontainers, not a pre-existing Compose stack.
  - Runtime config without redeploy: DB-backed config store with a TTL cache, not env var restarts.
  - Zero-downtime index creation: `CREATE INDEX CONCURRENTLY`, not a maintenance window.
  - Idempotent writes: `ON CONFLICT DO NOTHING / DO UPDATE`, not check-then-insert.
  - Batch processing with crash safety: transactional checkpoint cursor, not offset pagination.
- When a known pattern exists, use it and cite it. When no pattern exists, design the simplest thing that could work and document the trade-offs explicitly.
- Production limitations that are intentionally out of scope (pub/sub cache invalidation, rolling deploy coordination, backfill throttling) must be documented in `ARCHITECTURE.md#whats-intentionally-omitted`, not silently absent.
- Dev tooling (pgAdmin, debug endpoints) must not start by default. Use Docker Compose profiles (`--profile tools`) to keep the default `up` surface minimal.

---

## Cloud-native on AWS with Terraform

### Ask first, build second

If a requirement is ambiguous — choice of runtime, DB tier, networking topology, cost constraints — ask a clarifying question before writing any code or Terraform. A wrong assumption costs more to undo than a 30-second question costs to ask.

### Community modules first

Use the [terraform-aws-modules](https://github.com/terraform-aws-modules) community modules for all standard AWS resources. Do not hand-roll VPC, ECS, RDS, or ECR resources.

| Resource | Module |
|---|---|
| VPC | `terraform-aws-modules/vpc/aws ~> 6.0` |
| ECS cluster + service | `terraform-aws-modules/ecs/aws ~> 7.0` |
| RDS | `terraform-aws-modules/rds/aws ~> 7.0` |
| ECR | `terraform-aws-modules/ecr/aws ~> 3.0` |

Rationale: community modules encode AWS best practices (IAM, security groups, subnet routing), are actively maintained, and eliminate hundreds of lines of boilerplate. Hand-rolling these is only justified when the module cannot express a required configuration — document why if that happens.

Pin module versions with `~>` (pessimistic constraint) to allow patch updates but block breaking major/minor changes.

### Cost posture: cheap but not fragile

Default to the lowest-cost option that does not create operational debt:

| Concern | Default choice | Upgrade path |
|---|---|---|
| Container runtime | ECS Fargate (no EC2 to patch) | ECS on EC2 Spot if cost dominates |
| Database | RDS Postgres `db.t4g.small` Single-AZ for non-prod, `db.t4g.medium` Multi-AZ for prod | Aurora Serverless v2 if workload is spiky |
| Secrets | RDS-managed password in Secrets Manager (`manage_master_user_password = true`) | SSM Parameter Store for non-sensitive config |
| Load balancing | ALB (HTTP/HTTPS, path routing) | NLB only if TCP/UDP or extreme throughput needed |
| Caching | None until measured. Add ElastiCache only when a DB query is proven to be the bottleneck | — |
| Object storage | S3 Standard; lifecycle rules to IA/Glacier for old data | — |

Managed services are preferred when the management overhead saved exceeds the fee. Document the trade-off when choosing self-managed.

### Terraform structure

- Single root module with `terraform.tfvars` per environment (`dev.tfvars`, `prod.tfvars`) and Terraform workspaces to isolate state. No separate root module per environment — that is duplication.
- For a single-app repository, a flat `main.tf` calling community modules directly is preferred over local `modules/` subdirectories. Local modules are only justified when the same configuration is reused across multiple root modules.
- Remote state in S3 + DynamoDB lock table. Never local state outside of throwaway experiments.
- `terraform plan` output must be reviewed before every `apply` in prod. CI runs `plan` on PR, `apply` only on merge to `main`.

### Networking defaults

- VPC with public, private, and intra (isolated) subnet tiers.
- **2 AZs is the default** — sufficient for HA at lower cost. Add a third AZ only when the workload explicitly requires it (e.g. regulatory requirement, or measured availability gap).
- Application containers run in private subnets. Only the ALB is in the public subnet. RDS is in intra subnets (no internet route at all — stricter than private).
- NAT Gateway: one shared in non-prod (cost saving ~$32/mo vs one-per-AZ). One per AZ in prod for AZ-level HA. Document this asymmetry in tfvars comments.
- No bastion hosts. Use AWS Systems Manager Session Manager for DB access.

### Container image hygiene — shift left

- Images are built in CI and pushed to ECR. Never build on the deployment host.
- Tag images with the Git commit SHA prefix (`sha-<short-sha>`). Never deploy `latest` to staging or prod. Use `IMMUTABLE` tag mutability in ECR to prevent silent overwrites.
- ECR lifecycle policy: keep last 10 tagged images, expire untagged after 1 day.
- Multi-stage Dockerfiles: build stage installs deps, final stage copies only the artifact. No build tools in the runtime image.
- Shift-left security checks in CI, before the image is pushed:
  - Run `trivy image` (or equivalent) on the built image. Fail the pipeline on CRITICAL CVEs.
  - Enable `scan_on_push = true` in ECR for a second pass using AWS Basic Scanning (free).
  - Pin base image digests (`FROM python:3.12-slim@sha256:...`) in production Dockerfiles only when digest renewal is automated (e.g. Renovate or Dependabot). Without automation, a stale digest is worse than a fresh tag — use tag + Trivy CVE scan instead.
- Do not run containers as root. Set `USER` in the Dockerfile to a non-root UID.

### Secrets and config

- Secrets (DB passwords) use RDS-managed rotation via `manage_master_user_password = true`. RDS generates, stores, and rotates the password in Secrets Manager automatically — no `random_password` resource, no rotation lambda to maintain.
- Non-sensitive config (feature flags, batch sizes) lives in ECS task definition environment variables or SSM Parameter Store.
- Application reads secrets via ECS secrets injection (`secrets` block in task definition). The app receives a plain environment variable at startup — no AWS SDK calls needed in application code.
- Never store secrets in tfvars, `.env` files committed to source control, or Terraform state (use `manage_master_user_password` to avoid this for RDS).

### Zero-downtime deployments

- ECS rolling update with `deployment_minimum_healthy_percent = 100` and `deployment_maximum_percent = 200`. This keeps full capacity during deploy — a new task must pass health checks before the old one is stopped.
- Database migrations run as a one-off ECS task (same image as the app, command override) before the new app version starts. No separate migration container to maintain.
- Schema changes follow the expand → dual-write → backfill → switch → contract pattern. A deploy never assumes the old schema is gone.
- **pgroll as an alternative**: [pgroll](https://github.com/xataio/pgroll) automates the expand/contract lifecycle with instant rollback support. Consider it when the manual pattern becomes operationally expensive or when multiple teams share the same database.
- ALB health check path is `/health`. Healthy threshold: 2 consecutive successes before traffic is routed to a new task.
- `ignore_task_definition_changes = true` on the ECS service prevents `terraform apply` from rolling back the image tag after CI has deployed a newer one.

### Observability

Two supported stacks — choose based on team preference and cost tolerance:

**Option A — AWS-native (lower operational overhead)**
- Structured JSON logs from the application via the `awslogs` log driver. No sidecar needed.
- CloudWatch Container Insights for ECS CPU/memory metrics (enable per cluster).
- RDS Performance Insights with 7-day free retention.
- CloudWatch Alarms on: ALB 5xx rate, ECS task count below desired, RDS CPU > 80%, free storage < 20%.
- Grafana connects to CloudWatch as a data source for dashboards and alerting. Use [Amazon Managed Grafana](https://aws.amazon.com/grafana/) or self-hosted Grafana on ECS.

**Option B — Open source stack (more control, more ops)**
- Application exposes a `/metrics` endpoint (Prometheus format).
- Prometheus scrapes ECS tasks via ECS service discovery or a sidecar exporter.
- Grafana connects to Prometheus for application metrics and to CloudWatch for AWS infra metrics.
- Loki for log aggregation (replaces CloudWatch Logs for application logs).
- Use this stack when you need cross-cloud portability or when CloudWatch costs are prohibitive at scale.

**Default**: start with Option A. Switch to Option B when CloudWatch costs exceed the operational cost of running the open source stack, or when cross-cloud portability is required.

No custom dashboards until the default CloudWatch metrics prove insufficient.

### IAM

- ECS task role: least privilege. Grant only the specific Secrets Manager ARNs and SSM paths the task needs.
- `GetAuthorizationToken`, `RegisterTaskDefinition`, and `DescribeTaskDefinition` have no resource scope — this is an AWS API limitation. Document it inline rather than silently using `*`.
- Separate task execution role (pulls image, writes logs) from task role (app runtime permissions). They are different things.
- Terraform IAM resources use `aws_iam_policy_document` data sources, not inline JSON strings.
- GitHub Actions uses OIDC federation (`aws-actions/configure-aws-credentials`). No long-lived access keys stored in GitHub secrets. Trust scoped to `refs/heads/main` only.
