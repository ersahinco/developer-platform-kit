# Deployment

## Pipelines

Two pipelines with separate triggers and responsibilities.

### infra.yml — infrastructure

Triggered by changes to `infra/**`.

| Event | Jobs |
|---|---|
| Pull request | lint-and-validate → plan-dev (posted as PR comment) |
| Push to main | lint-and-validate → apply-dev (auto) → apply-prod (manual approval) |

Terraform owns: VPC, ECS cluster/service, RDS, ECR, ALB, IAM, task definition shape.
It does not own the image tag — that is patched at release time by `app.yml`.

### app.yml — release

Triggered by changes to `app/**`, `db/**`, `tests/**`, `scripts/**`.

| Event | Jobs |
|---|---|
| Pull request | validate-and-test only |
| Push to main | validate-and-test → build-and-push → dev-migrate → dev-deploy → prod-migrate → prod-deploy |

`prod-migrate` and `prod-deploy` require manual approval in GitHub Environments.

---

## GitHub Environments

Five environments — create these in **Settings → Environments** before the first run.

| Environment | Pipeline | Approval | Secret |
|---|---|---|---|
| `dev-infra` | infra.yml | none | `AWS_ROLE_ARN` |
| `prod-infra` | infra.yml | required | `AWS_ROLE_ARN` |
| `dev-deploy` | app.yml | none | `AWS_ROLE_ARN` |
| `prod-migrate` | app.yml | required | `AWS_ROLE_ARN` |
| `prod-deploy` | app.yml | required | `AWS_ROLE_ARN` |

`AWS_ROLE_ARN` values:

| Environment | Value |
|---|---|
| `dev-infra`, `dev-deploy` | `arn:aws:iam::691627364817:role/db-migration-example-dev-github-actions` |
| `prod-infra`, `prod-migrate`, `prod-deploy` | `arn:aws:iam::691627364817:role/db-migration-example-prod-github-actions` |

No other secrets or variables are needed. All resource names follow the
`db-migration-example-{env}` convention and are inlined in the workflows.
Subnet and security group IDs are resolved at runtime by tag.

---

## Bootstrap — one-time setup per AWS account

These steps are run once before the first `terraform apply`. They create the
resources Terraform itself depends on (state backend, OIDC provider).

```bash
make bootstrap           # creates S3 state bucket, DynamoDB lock table, OIDC provider
make infra-apply-iam-dev  # targeted apply: IAM role only — required before first full plan
make infra-apply-dev      # full dev apply
make infra-apply-iam-prod # targeted apply: IAM role only for prod
make infra-apply-prod     # full prod apply
```

See `Makefile` for all available targets (`make help`).

---

## Naming convention

All AWS resources follow `db-migration-example-{env}`. This is the single
source of truth — no variables or secrets are needed in the pipelines beyond
`AWS_ROLE_ARN`.

| Resource | dev | prod |
|---|---|---|
| ECS cluster | `db-migration-example-dev` | `db-migration-example-prod` |
| ECS service | `app` | `app` |
| Task family (app) | `db-migration-example-dev` | `db-migration-example-prod` || Task family (worker) | `db-migration-example-dev-worker` | `db-migration-example-prod-worker` |
| Task family (liquibase) | `db-migration-example-dev-liquibase` | `db-migration-example-prod-liquibase` |
| ECR repos | `db-migration-example-dev/{app,worker,liquibase}` | `db-migration-example-prod/{app,worker,liquibase}` |
| IAM role | `db-migration-example-dev-github-actions` | `db-migration-example-prod-github-actions` |

---

## Image tagging

Images are tagged `sha-{git-sha}` and pushed to both dev and prod ECR repos
from the same build. `latest` is never used — ECR tag mutability is set to
`IMMUTABLE`.

Terraform registers task definitions with a `:placeholder` image tag.
`app.yml` patches the real SHA tag at release time via
`amazon-ecs-render-task-definition` — infra apply never touches the image tag.

---

## Failure recovery and re-runs

### What happens if prod-deploy fails after prod-migrate

No automatic rollback occurs — and none is needed. The migration is always an
expand-phase change (additive: new table or column alongside the old one). The
old app version still running in ECS is fully compatible with the new schema
because nothing was removed. ECS rolling deploy behaviour:

- If new tasks fail health checks, ECS stops them and keeps the old tasks
  running. Old app code + new schema = safe.
- If the backfill worker job times out in CI, the ECS task continues running
  independently. The worker uses a transactional cursor checkpoint — re-running
  it on the next pipeline execution resumes from where it stopped.

The contract phase (dropping the old column) is always a separate, later deploy.
A failed prod-deploy can never leave the DB in a state incompatible with the
currently running app.

**To recover**: fix the root cause, push a new commit (or re-run the workflow
manually via `workflow_dispatch`). The pipeline will re-run from
`validate-and-test`. All steps are safe to repeat:

| Step | Re-run behaviour |
|---|---|
| Liquibase migrate | Skips already-applied changesets (`DATABASECHANGELOG`) |
| ECS service deploy | Detects same image tag already active, no-ops the rolling update |
| Backfill worker | Resumes from transactional cursor checkpoint |

### Avoiding duplicate resources on re-run

`register-task-definition` always creates a new ECS revision — this is
expected and harmless. ECS keeps the previous revisions; only the latest active
revision is used. Old revisions are not billed and do not affect running tasks.

`run-task` for Liquibase and the backfill worker are both safe to call multiple
times in the same pipeline run or across re-runs — idempotency is guaranteed by
Liquibase's changeset tracking and the worker's checkpoint cursor respectively.

---

## Sprint reset (dev environment)

To reset dev to a clean state:

```bash
cd infra
terraform init -backend-config="key=db-migration-example/dev.tfstate" -reconfigure
terraform destroy -var-file=dev.tfvars
terraform apply  -var-file=dev.tfvars
```

Then re-run the full runbook from step 2 in `README.md` against the fresh RDS instance.

---

## DB access and data seeding (deployed environments)

RDS is in intra subnets with no internet route. Access is via SSM port forwarding through a running ECS task — no bastion host needed.

### Prerequisites

```bash
brew install session-manager-plugin
```

### Open the tunnel

```bash
make db-tunnel ENV=dev        # forwards localhost:15432 → RDS:5432
make db-tunnel ENV=prod LOCAL_PORT=25432
```

The tunnel stays open until you Ctrl+C. Keep it running in a dedicated terminal.

### Get credentials

```bash
aws secretsmanager get-secret-value \
  --secret-id $(cd infra && terraform output -raw db_secret_arn) \
  --query SecretString --output text | python3 -m json.tool
```

### Connect with psql

```bash
SECRET=$(aws secretsmanager get-secret-value \
  --secret-id $(cd infra && terraform output -raw db_secret_arn) \
  --query SecretString --output text)

PGPASSWORD=$(echo $SECRET | python3 -c "import sys,json; print(json.load(sys.stdin)['password'])") \
  psql -h localhost -p 15432 -U app -d migration_example
```

### Seed data

`make db-seed` opens the SSM tunnel, fetches credentials from Secrets Manager, runs the seed script, and closes the tunnel — no manual steps needed:

```bash
make db-seed ENV=dev
make db-seed ENV=prod

# larger volume
make db-seed ENV=prod SEED_NUM_CUSTOMERS=50000 SEED_NUM_ORDERS=500000
```

`seed_data.py` is idempotent — it skips insertion if rows already exist. Volume is controlled by `SEED_NUM_CUSTOMERS` and `SEED_NUM_ORDERS` (defaults: 1,000 / 10,000). The tunnel uses port 15433 to avoid colliding with an open `db-tunnel` session on 15432.
