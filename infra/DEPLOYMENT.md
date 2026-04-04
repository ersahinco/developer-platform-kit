# Deployment Guide

This document covers everything needed to go from a clean AWS account to a running environment, and how the CI/CD pipeline operates day-to-day.

---

## Prerequisites

- AWS CLI configured with credentials for account `691627364817`
- Terraform >= 1.11.0 (`brew install terraform`)
- Docker Desktop running (for local builds during bootstrap)

---

## 1. One-time AWS account bootstrap

These steps run once per AWS account, not per environment.

### 1.1 Terraform remote state

```bash
aws s3 mb s3://db-migration-example-tfstate-691627364817 \
  --region eu-central-1

aws s3api put-bucket-versioning \
  --bucket db-migration-example-tfstate-691627364817 \
  --versioning-configuration Status=Enabled

aws dynamodb create-table \
  --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-central-1
```

### 1.2 GitHub Actions OIDC provider

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  --region eu-central-1
```

This enables GitHub Actions to assume AWS roles without long-lived access keys.

---

## 2. First Terraform apply (bootstrap)

Infra is deployed via the `infra.yml` CI pipeline — not from local. The pipeline runs on every push to `main` that touches `infra/**`:

- PR opened → static checks + `terraform plan` posted as a PR comment
- Merged to `main` → `terraform apply` to dev (auto), then prod (manual approval)

The only time you run Terraform locally is the one-time bootstrap before CI exists, or to recover from a broken state.

### 2.1 Bootstrap (one-time, before CI is wired up)

```bash
cd infra

# dev
terraform init -backend-config="key=db-migration-example/dev.tfstate" -reconfigure
terraform plan -var-file=dev.tfvars -out=dev.tfplan
terraform apply dev.tfplan

# prod (when ready)
terraform init -backend-config="key=db-migration-example/prod.tfstate" -reconfigure
terraform plan -var-file=prod.tfvars -out=prod.tfplan
terraform apply prod.tfplan
```

### 2.2 GitHub Environments for the infra pipeline

Create two environments in **GitHub → Settings → Environments**:

| Environment | Protection rule |
|---|---|
| `infra-dev` | None (auto-applies on merge) |
| `infra-prod` | Required reviewers |

Set `AWS_ROLE_ARN` on each environment (dev and prod roles can be the same role if scoped broadly enough, or separate roles per environment for stricter isolation).

### 2.3 Capture outputs for the app pipeline secrets

After the first apply, collect the values needed for `deploy.yml`:

```bash
cd infra
terraform init -backend-config="key=db-migration-example/dev.tfstate" -reconfigure
terraform output -json
```

| Terraform output | GitHub secret name |
|---|---|
| `github_actions_role_arn` | `AWS_ROLE_ARN` |
| `ecr_app_repository_url` | used to derive `ECR_REGISTRY` (strip the repo path) |
| `ecs_cluster_name` | `ECS_CLUSTER` |
| `app_service_name` | `APP_SERVICE_NAME` |
| `worker_task_definition_arn` | `WORKER_TASK_DEF_ARN` |
| `liquibase_task_definition_arn` | `LIQUIBASE_TASK_DEF_ARN` |
| `private_subnet_ids` (first element) | `PRIVATE_SUBNET_ID` |
| `app_security_group_id` | `APP_SG_ID` |
| `db_secret_arn` | `DB_SECRET_ARN` |

`APP_TASK_FAMILY` is not a Terraform output — it is deterministic: `db-migration-example-<environment>-app` (e.g. `db-migration-example-dev-app`). Set this as a secret manually after the first apply.

---

## 3. GitHub Environments and secrets

Go to **GitHub → Settings → Environments** and create:

| Environment | Protection rule | Used by |
|---|---|---|
| `infra-dev` | None | infra pipeline — auto-applies on merge |
| `infra-prod` | Required reviewers | infra pipeline — prod apply gate |
| `dev` | None | app pipeline — auto-deploys on merge |
| `production-migrate` | Required reviewers | app pipeline |
| `production-deploy` | Required reviewers | app pipeline |

Set the secrets listed in section 2.3 on each environment. Secrets set at the environment level override repo-level secrets, which allows dev and prod to point at different clusters.

---

## 4. CI/CD pipelines

Two separate pipelines run on every push to `main`.

### infra.yml — infrastructure pipeline

Triggers on changes to `infra/**`.

```
lint-and-validate   (fmt, validate, tflint, checkov — no AWS needed)
      │
      ├── plan-dev      (PR only — posts terraform plan diff as PR comment)
      │
      ├── apply-dev     (merge to main — auto)
      │
      └── apply-prod    (merge to main — manual approval required)
```

### deploy.yml — app + data pipeline

Triggers on changes to `app/**`, `db/**`, `tests/**`, `scripts/**`.

```
validate-and-test
      │
build-and-push  (tags image: sha-<commit>, trivy CRITICAL scan before push)
      │
dev-migrate     (Liquibase update on dev RDS — one-off ECS task)
      │
dev-deploy      (rolling ECS update, waits for stability)
      │
prod-migrate    ← manual approval required  (Liquibase update)
      │
prod-deploy     ← manual approval required  (rolling ECS update)
```

### Job details

**validate-and-test** — spins up Postgres and PgBouncer service containers, runs Liquibase, seeds 200 customers / 1,000 orders, starts the app, runs the full pytest suite. Hermetic — no AWS credentials needed.

**build-and-push** — builds the `app/`, `worker/`, and `db/` (Liquibase) Docker images, tags all three with `sha-<commit>`, scans each with `trivy image --severity CRITICAL` (fails on any CRITICAL CVE before push), then pushes to ECR. Uses OIDC — no long-lived AWS keys.

**dev-migrate / prod-migrate** — a one-off ECS task inside the VPC that runs `liquibase update`. Connects directly to RDS (not via PgBouncer) — DDL requires a persistent session connection.

**prod-deploy** — rolling ECS update. Also triggers the backfill worker as a one-off Fargate task. The worker connects directly to RDS (bypasses pgbouncer — backfill transactions are long-running and incompatible with transaction-mode pooling) and exits when done. Monitor in CloudWatch Logs at `/ecs/db-migration-example-prod/worker`.

---

## 5. Local infra development workflow

You don't need to apply to AWS to validate most changes. Run these locally before pushing a branch:

```bash
git add -A && git commit -m "ci: trigger pipeline"

cd infra

# formatting
terraform fmt -check -recursive

# syntax + type errors (no AWS needed — backend=false skips state)
terraform init -backend=false
terraform validate

# provider-specific lint (wrong instance types, deprecated args, etc.)
tflint --init && tflint

# security misconfigs (open SGs, unencrypted storage, missing tags)
checkov -d .
```

Install the tools once:
```bash
brew install terraform tflint checkov
```

Push your branch → CI runs `terraform plan` against the real dev state and posts the diff as a PR comment. That plan output is your primary review artifact before merge.

The ECS service has `ignore_task_definition_changes = true` — Terraform will not roll back the image tag that CI has deployed. It only manages infrastructure changes (CPU, memory, security groups, etc.).

---

## 6. Rollback

| Situation | Action |
|---|---|
| Bad app deploy | Re-run the deploy job with the previous commit SHA, or `aws ecs update-service --force-new-deployment` with the previous task definition revision |
| Bad migration (pre-contract) | Migrations are additive — no rollback needed. The old app version still works against the expanded schema |
| Backfill went wrong | `TRUNCATE order_contact_email; UPDATE backfill_progress SET last_order_id=0, rows_processed=0;` then re-run the worker |
| READ_MODE switch | `uv run python scripts/set_runtime_config.py read-mode legacy` — instant, no restart |
| Contract applied (irreversible) | Restore from RDS snapshot taken before step 8 of the runbook |

---

## 7. Destroying an environment

```bash
cd infra
terraform init -backend-config="key=db-migration-example/dev.tfstate" -reconfigure

# Disable deletion protection first if it was enabled
terraform apply -var-file=dev.tfvars -var="rds_multi_az=false"

terraform destroy -var-file=dev.tfvars
```

Run destroy locally — do not automate environment teardown in CI.
