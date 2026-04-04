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
It does not own the image tag — that is patched at release time by `deploy.yml`.

### deploy.yml — release

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
| `dev-deploy` | deploy.yml | none | `AWS_ROLE_ARN` |
| `prod-migrate` | deploy.yml | required | `AWS_ROLE_ARN` |
| `prod-deploy` | deploy.yml | required | `AWS_ROLE_ARN` |

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

### 1. Create the Terraform state bucket and lock table

```bash
aws s3api create-bucket \
  --bucket db-migration-example-tfstate-691627364817 \
  --region eu-central-1 \
  --create-bucket-configuration LocationConstraint=eu-central-1

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

### 2. Register the GitHub Actions OIDC provider

Run once per AWS account — not per environment.

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

### 3. Run the first terraform apply locally

The GitHub Actions role does not exist yet, so the pipeline cannot run.
Bootstrap with local credentials that have broad IAM permissions:

```bash
cd infra
terraform init -backend-config="key=db-migration-example/dev.tfstate"
terraform apply -var-file=dev.tfvars
```

After this apply the `dev-github-actions` role exists. Set `AWS_ROLE_ARN` in
the `dev-infra` and `dev-deploy` GitHub Environments, then the pipeline can
manage itself from that point on.

Repeat for prod:

```bash
terraform init -backend-config="key=db-migration-example/prod.tfstate" -reconfigure
terraform apply -var-file=prod.tfvars
```

---

## Naming convention

All AWS resources follow `db-migration-example-{env}`. This is the single
source of truth — no variables or secrets are needed in the pipelines beyond
`AWS_ROLE_ARN`.

| Resource | dev | prod |
|---|---|---|
| ECS cluster | `db-migration-example-dev` | `db-migration-example-prod` |
| ECS service | `db-migration-example-dev-app` | `db-migration-example-prod-app` |
| Task family (app) | `db-migration-example-dev` | `db-migration-example-prod` |
| Task family (worker) | `db-migration-example-dev-worker` | `db-migration-example-prod-worker` |
| Task family (liquibase) | `db-migration-example-dev-liquibase` | `db-migration-example-prod-liquibase` |
| ECR repos | `db-migration-example-dev/{app,worker,liquibase}` | `db-migration-example-prod/{app,worker,liquibase}` |
| IAM role | `db-migration-example-dev-github-actions` | `db-migration-example-prod-github-actions` |

---

## Image tagging

Images are tagged `sha-{git-sha}` and pushed to both dev and prod ECR repos
from the same build. `latest` is never used — ECR tag mutability is set to
`IMMUTABLE`.

Terraform registers task definitions with a `:placeholder` image tag.
`deploy.yml` patches the real SHA tag at release time via
`amazon-ecs-render-task-definition` — infra apply never touches the image tag.

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
