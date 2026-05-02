# Deployment

This project uses one AWS account/region and two Terraform roots split by
lifecycle.

- `infra/platform`: VPC networking, VPC endpoints, account/domain lookups, and
  GitHub Actions OIDC/CI IAM.
- `infra/app`: RDS, ECS compute, ECR repositories, WAF-protected ALB/API edge,
  S3 data hub, workload jobs/queues, app IAM, CloudWatch app alarms, and optional
  Grafana/Loki/Prometheus observability.

Safe rollout does not come from duplicating infrastructure. It comes from additive schema changes, separate task definitions, runtime read/write switches, and one-off worker tasks running against the same database.

## Current platform contract

- Base stack: one VPC, one public WAF-protected ALB/TLS/DNS entrypoint, one ECS cluster, one long-running app service with PgBouncer, one PostgreSQL database, and split platform/app Terraform state.
- Reference workload: the app, Liquibase task, and backfill worker all operate inside that same stack. Rollout stays in place through additive schema changes, task definition updates, runtime switches, and one-off tasks.
- Public-edge rule: any public-facing ALB must be associated with WAF. VPC endpoints, ECS Exec/SSM access, and similar operator conveniences can remain separate capabilities.
- Future additions: observability, extra operator tooling, and workload-specific jobs should stay as extensions unless they become mandatory for every workload that uses this repo.

## Pipeline shape

GitHub Actions workflows are split by review boundary. Cloud-changing steps
only run after a separate manual trigger:

- `infra-plan.yml`
  PR, push, manual: lint + validate + platform plan + app plan, then publish plan output.
- `infra-apply.yml`
  Manual: apply reviewed platform and app plan artifacts by workflow run ID.
- `app-build.yml`
  PR and push: validate and test. Manual: validate → build → scan → push images.
- `app-deploy.yml`
  Manual: migrate → deploy → verify → register support task definitions → run backfill worker.

## GitHub setup

Create one GitHub Environment named `aws` and store:

- `AWS_ROLE_ARN`

That is the only AWS secret the workflows need. Other runtime values are resolved from the stack at deploy time.

Cloud-changing workflow jobs do not run automatically on merge. Review the
`Infra Plan` output before running `Infra Apply`, and review the `App Build`
logs and image tag before running `App Deploy`. This does not rely on paid
GitHub Environment required reviewer gates.

## Bootstrap

Run this sequence once per fresh AWS account before the first full split-root
apply. The bootstrap path exists because Terraform cannot create the remote
state bucket or the GitHub Actions role before it can initialize and
authenticate.

Prerequisites:

- AWS credentials for the target account, with permissions to create S3,
  DynamoDB, IAM, ECR, Secrets Manager, ACM, Route 53, VPC, RDS, ECS, and
  CloudWatch resources.
- The target region is `eu-central-1`.
- A public Route 53 hosted zone already exists for `root_domain` in
  `infra/platform/stack.tfvars` (currently `ersahinco-sandbox.eu`).
- The GitHub repository has an Environment named `aws`.
- GitHub CLI access can set environment secrets for the repository.

Set the operator-owned values first:

```bash
$EDITOR infra/platform/stack.tfvars
$EDITOR infra/app/stack.tfvars
```

At minimum, confirm:

- `root_domain` in `infra/platform/stack.tfvars` matches the public hosted zone.
- `api_token_secret_name` is the Secrets Manager name the ALB auth rule should
  read, if overridden in `infra/app/stack.tfvars`.

For a different AWS account than the checked-in sandbox, also align the
account-specific Terraform backend values before bootstrapping:

- `ACCOUNT_ID` in `Makefile`
- `bucket` in `infra/platform/versions.tf`
- `bucket` in `infra/app/versions.tf`

Terraform backend blocks cannot read normal Terraform variables, so the backend
bucket name is intentionally a literal value.

Create the API token secret out of band so the token value never lands in
Terraform state or tfvars:

```bash
aws secretsmanager create-secret \
  --name aws-sdlc-containers/api-token \
  --region eu-central-1 \
  --secret-string "$(openssl rand -hex 32)"
```

If the secret already exists, leave it in place. To check:

```bash
aws secretsmanager describe-secret \
  --secret-id aws-sdlc-containers/api-token \
  --region eu-central-1
```

Create the Terraform backend bootstrap resources:

```bash
make bootstrap
```

This target is idempotent. It creates or confirms:

- S3 state bucket: `aws-sdlc-containers-tfstate-<account-id>`
- S3 bucket versioning
- DynamoDB table: `terraform-locks`
- IAM OIDC provider: `token.actions.githubusercontent.com`

Terraform uses two state objects:

```bash
aws-sdlc-containers/platform.tfstate
aws-sdlc-containers/app.tfstate
```

The active backend lock is Terraform's S3 native lockfile through
`use_lockfile = true` in each root's `versions.tf`. The `terraform-locks`
DynamoDB table is still bootstrapped for compatibility with older runbooks and
IAM policy surfaces, but the current backends do not set `dynamodb_table`.

Confirm the Route 53 zone can be found before applying the stack:

```bash
ROOT_DOMAIN=ersahinco-sandbox.eu
aws route53 list-hosted-zones-by-name \
  --dns-name "$ROOT_DOMAIN" \
  --max-items 1
```

The full Terraform stack creates the ACM certificate for
`api.<root_domain>`, the DNS validation records, and the final Route 53 alias to
the public load balancer. The hosted zone itself is intentionally a
pre-existing account/domain prerequisite.

Create platform first from local credentials:

```bash
make infra-platform-plan
make infra-platform-apply
```

This creates the GitHub Actions IAM role and policies that
`.github/workflows/infra-plan.yml`, `.github/workflows/infra-apply.yml`,
`.github/workflows/app-build.yml`, and `.github/workflows/app-deploy.yml`
assume through OIDC, along with VPC networking and shared platform outputs.

Store the role ARN in the GitHub Environment named `aws`:

```bash
gh secret set AWS_ROLE_ARN \
  --env aws \
  --repo ersahinco/aws-sdlc-containers \
  --body arn:aws:iam::<account-id>:role/aws-sdlc-containers-github-actions
```

Check it with:

```bash
gh secret list \
  --env aws \
  --repo ersahinco/aws-sdlc-containers
```

After that, deploy the app root:

```bash
make infra-app-plan
make infra-app-apply
```

The full split apply creates live infrastructure and cost-bearing resources
including VPC networking, NAT, RDS, ALB, ECS, CloudWatch logs, DNS, and
certificates.

Useful bootstrap checks:

```bash
aws s3api get-bucket-versioning \
  --bucket aws-sdlc-containers-tfstate-<account-id>

aws s3api head-object \
  --bucket aws-sdlc-containers-tfstate-<account-id> \
  --key aws-sdlc-containers/platform.tfstate

aws s3api head-object \
  --bucket aws-sdlc-containers-tfstate-<account-id> \
  --key aws-sdlc-containers/app.tfstate

aws iam list-open-id-connect-providers

aws iam get-role \
  --role-name aws-sdlc-containers-github-actions

make infra-plan
```

Operator-set values live in `infra/platform/stack.tfvars` and
`infra/app/stack.tfvars`.

## Naming

Resources use the project prefix `aws-sdlc-containers`.

- ECS cluster: `aws-sdlc-containers`
- ECS service: `app`
- App task family: `aws-sdlc-containers`
- Worker task family: `aws-sdlc-containers-worker`
- Liquibase task family: `aws-sdlc-containers-liquibase`
- ECR repos:
  `aws-sdlc-containers/{app,worker,data-export-job,order-event-consumer,liquibase,pgbouncer,firelens}`
- API hostname: `api.<root_domain>`

## Rollout model

Rollout stays inside the same cluster and the same database:

1. Build and push new images.
2. Run Liquibase against the current database.
3. Deploy the new app task definition to the existing ECS service.
4. Verify the deployed app with `/ready`, `/metrics`, runtime mode, and ECS
   task/image checks.
5. Run the backfill worker as a one-off task if the migration requires it.
6. Advance `WRITE_MODE` and `READ_MODE` through the runbook.

This keeps the project lean while still supporting safe schema evolution.

The FireLens image is app-owned and built by the same app build workflow as the
workload images. On a fresh account, create the ECR repositories with the app
infra apply, run `app-build.yml` to push the selected `sha-...` tag, then deploy
or restart ECS services so every task can pull the matching `firelens` image.

## No multi-AZ by default

This stack is deliberately not Multi-AZ for either ECS or RDS.

- ECS runs with a single desired app task by default.
- RDS stays single-AZ.
- The VPC still spans two AZs because RDS subnet groups require that shape, but the data layer itself is not deployed in Multi-AZ mode.

## Common commands

```bash
make infra-plan
make infra-apply
make app-deploy
make post-deploy-verify
make db-tunnel
make grafana-tunnel
make db-exec
make db-seed
make api-get-order ORDER_ID=1
```

## DB access

RDS remains private. Access is through SSM port forwarding via the running ECS task:

```bash
make db-tunnel
```

Then connect with:

- Host: `localhost`
- Port: `15432`
- Database: `aws_sdlc_containers`

## Grafana access

The ECS Grafana stack remains private. Access it through SSM port forwarding:

```bash
make grafana-tunnel
```

Then open `http://localhost:3000` and use the Grafana admin secret configured
for the stack.

## Failure recovery

Because rollout is additive and in-place:

- A failed app deploy does not invalidate the current database schema.
- Re-running Liquibase is safe because changesets are tracked.
- Re-running the worker is safe because it is checkpointed and idempotent.
- For throttled repair or replay, run the worker with `BACKFILL_MAX_BATCHES` set
  to a small positive integer. The worker exits 0 after that many committed
  batches and resumes from the checkpoint on the next run.
- The irreversible step is still the contract migration that removes the old column.

Use these checkpoints during the migration rollout:

| Phase | Before advancing | If the step fails | Rollback path |
|---|---|---|---|
| Expand | `terraform plan` is reviewed, app is healthy, and a DB snapshot policy exists for the stack. | Stop before changing runtime modes. Re-run Liquibase after fixing the failed changeset or connectivity issue. | No app rollback is needed because the old schema is still intact. |
| Dual-write | `order_contact_email` exists and the currently deployed app version supports `WRITE_MODE=dual`. | Set `WRITE_MODE=legacy` through the admin API if writes behave unexpectedly. | Reads still use the old column, so returning to `legacy` writes restores the old behavior. |
| Backfill | `WRITE_MODE=dual` is active and the worker task definition points at the intended image tag. | Re-run the worker task. It is checkpointed and uses idempotent inserts. | Leave `READ_MODE=legacy`; the app continues reading from the old column. |
| Switch reads | Backfill has completed and tests pass in the switch phase. | Set `READ_MODE=legacy` through the admin API. | Dual-write keeps both locations current, so read rollback is safe. |
| New writes | `READ_MODE=new` has been verified and all app tasks are on the compatible version. | Set `WRITE_MODE=dual` if new-only writes expose an issue before contract. | The old column still exists, so dual-write restores rollback safety. |
| Contract | A DB snapshot exists and no running app version needs `orders.billing_email`. | Stop deployment and restore from snapshot only if the contract has already removed required data. | This is the first irreversible step. Do not apply it until rollback through runtime flags is no longer needed. |

When recovering a failed GitHub Actions deployment, prefer rerunning the failed
job with the same commit SHA instead of rebuilding from a different commit. The
ECR image tags are immutable `sha-<commit>` tags, so the task definitions should
continue to reference the exact images that were validated earlier in the
pipeline.

If a deploy reaches ECS but causes unhealthy targets, target 5xxs, or latency
alarms, use `docs/runbooks/ecs-deploy-rollback.md` to identify the previous
healthy task definition revision and roll the app service back without changing
database state.

After an app deploy reaches ECS, run the post-deploy verifier before advancing
runtime modes or relying on the new task image:

```bash
make post-deploy-verify
```

The target checks `/health`, `/ready`, `/metrics`, `READ_MODE`, `WRITE_MODE`,
the active ECS task family, and the deployed app image when
`EXPECTED_IMAGE_TAG` or `EXPECTED_APP_IMAGE` is provided. The GitHub Actions
deploy job runs the same verifier immediately after updating the app service
and before registering one-off worker or data export task definitions.

## Canonical source

This file is the operator-facing source of truth for the current split-root rollout. See `architecture.md` for the design rationale and extension boundaries.
