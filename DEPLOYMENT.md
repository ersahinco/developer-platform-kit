# Deployment

This project intentionally uses a single AWS stack.

- One ECS cluster
- One PostgreSQL database
- One public API hostname
- One Terraform state

Safe rollout does not come from duplicating infrastructure. It comes from additive schema changes, separate task definitions, runtime read/write switches, and one-off worker tasks running against the same database.

## Pipeline shape

Two GitHub Actions workflows remain, but both target the same stack:

- `infra.yml`
  PR: lint + `terraform plan`
  Merge to `main`: `terraform apply`
- `app.yml`
  PR: validate and test
  Merge to `main`: validate → build → push → migrate → deploy → backfill worker

## GitHub setup

Create one GitHub Environment named `aws` and store:

- `AWS_ROLE_ARN`

That is the only AWS secret the workflows need.

## Bootstrap

Run these once per AWS account:

```bash
make bootstrap
make infra-apply-iam
make infra-apply
```

Terraform uses one state key:

```bash
aws-sdlc-containers/stack.tfstate
```

The main variables live in `infra/stack.tfvars`.

## Naming

Resources use the single stack prefix `aws-sdlc-containers`.

- ECS cluster: `aws-sdlc-containers`
- ECS service: `app`
- App task family: `aws-sdlc-containers`
- Worker task family: `aws-sdlc-containers-worker`
- Liquibase task family: `aws-sdlc-containers-liquibase`
- ECR repos: `aws-sdlc-containers/{app,worker,liquibase,pgbouncer}`
- API hostname: `api.<root_domain>`

## Rollout model

Rollout stays inside the same cluster and the same database:

1. Build and push new images.
2. Run Liquibase against the current database.
3. Deploy the new app task definition to the existing ECS service.
4. Run the backfill worker as a one-off task if the migration requires it.
5. Advance `WRITE_MODE` and `READ_MODE` through the runbook.

This keeps the project lean while still supporting safe schema evolution.

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
make db-tunnel
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

## Failure recovery

Because rollout is additive and in-place:

- A failed app deploy does not invalidate the current database schema.
- Re-running Liquibase is safe because changesets are tracked.
- Re-running the worker is safe because it is checkpointed and idempotent.
- The irreversible step is still the contract migration that removes the old column.

## Canonical source

This file is the deployment source of truth.
