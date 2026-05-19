# Deployment

This project uses one AWS account and region with two Terraform roots split by
lifecycle:

- `infra/platform`: shared platform and bootstrap concerns
- `infra/app`: runtime resources such as RDS, ECS, ALB edge, jobs, messaging,
  storage, and alarms

Safe rollout comes from additive schema change, runtime switches, and one-off
tasks, not from duplicating infrastructure.

This doc owns current AWS delivery and operator flow. For the portable workload
contract, use [Platform Contract](platform-contract.md). For repo placement and
ownership boundaries, use [Architecture](architecture.md).

## Pipeline Shape

- `infra-plan.yml`: lint, validate, and publish reviewed Terraform plans
- `infra-apply.yml`: manually apply reviewed plan artifacts
- `app-build.yml`: validate, test, build, scan, and push images
- `app-deploy.yml`: migrate, deploy, verify, register support task definitions,
  and run the backfill worker

Terraform owns infrastructure shape. GitHub Actions owns app image rollout
after bootstrap. Keep that boundary explicit.

`platform/workloads.json` can identify what workloads exist and which one is
the primary edge service, but it should not own AWS rollout choreography. Task
registration, service update order, verification sequence, and support-job
execution remain delivery-edge behavior.

## GitHub Setup

Create one GitHub environment named `aws` with:

- `AWS_ROLE_ARN`

Useful variables:

- `AWS_REGION`
- `STACK_NAME`
- `ROOT_DOMAIN`
- `TF_STATE_BUCKET`
- `TF_PLATFORM_STATE_KEY`
- `TF_APP_STATE_KEY`

## Bootstrap

Prerequisites:

- AWS credentials with permissions to create the stack
- A public Route 53 hosted zone for `root_domain`
- A GitHub environment named `aws`

Create the API token secret out of band:

```bash
aws secretsmanager create-secret \
  --name "${STACK_NAME:-aws-sdlc-containers}/api-token" \
  --region "${AWS_REGION:-eu-central-1}" \
  --secret-string "$(openssl rand -hex 32)"
```

Create the backend bucket and OIDC provider:

```bash
make bootstrap
```

Apply platform first, then app:

```bash
make infra-platform-plan
make infra-platform-apply
make infra-app-plan
make infra-app-apply
```

## Rollout Model

1. Build and push images.
2. Run Liquibase against the current database.
3. Deploy the new ECS task definition.
4. Verify health, metrics, runtime modes, and image/task identity.
5. Run the backfill worker if the migration requires it.
6. Advance `WRITE_MODE` and `READ_MODE` through the rollout path.

This keeps the project lean while still supporting safe schema evolution.

## Common Commands

```bash
make infra-plan
make infra-apply
make app-deploy
make post-deploy-verify
make db-tunnel
make db-exec
make db-seed
```

## Access Patterns

RDS stays private. Use SSM port forwarding:

```bash
make db-tunnel
```

Local Grafana access:

```bash
make observability
```
