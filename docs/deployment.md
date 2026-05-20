# Deployment

Canonical AWS delivery and operator flow.

Use [Platform Contract](platform-contract.md) for portable workload rules and
[Architecture](architecture.md) for ownership boundaries.

## Scope

| Surface | Owns |
|---|---|
| `infra/platform` | shared platform bootstrap, network, GitHub OIDC |
| `infra/app` | RDS, ECS, ALB edge, jobs, messaging, storage, alarms |
| GitHub Actions | image build, rollout, verification, release evidence |

Safe rollout comes from additive schema change, runtime switches, and one-off
tasks, not duplicated infrastructure.

## Change Control Matrix

| Workflow | Trigger and reviewed input | Control boundary | Evidence |
|---|---|---|---|
| `app-build.yml` | Manual `workflow_dispatch` with `confirm_build=build` after PR review on the default branch | builds, scans, attests, and pushes immutable images only | `release-evidence-app-build-*` artifact and build summary |
| `app-deploy.yml` | Manual `workflow_dispatch` with approved immutable `image_tag` and `confirm_deploy=deploy` on the default branch | runs Liquibase, updates ECS services and support task definitions, verifies health, runs backfill if needed | `release-evidence-app-deploy-*` artifact and step summary |
| `infra-plan.yml` | pull request, main push, or manual run | produces reviewed Terraform plans without changing cloud resources | uploaded Terraform plan artifact and optional PR comment |
| `infra-apply.yml` | Manual `workflow_dispatch` with successful `plan_run_id` and `confirm_apply=apply` on the default branch | applies only reviewed Terraform plan artifacts for the current default-branch SHA | `release-evidence-infra-apply-*` artifact and step summary |

Rule: PRs prove correctness. Manual workflows promote a reviewed artifact or
reviewed plan. Every cloud-changing step leaves portable evidence.

## GitHub Setup

GitHub environment: `aws`

Required:

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

- AWS credentials with permission to create the stack
- public Route 53 hosted zone for `root_domain`
- GitHub environment named `aws`

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

## Review Loop

Use the same loop for deploys, applies, and drills:

```bash
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id> \
make incident-evidence
```

Checks:

1. App build: confirm branch, SHA, immutable `sha-...` image tag, and expected `release-evidence-app-build-*` artifacts.
2. App deploy: confirm Liquibase and deploy both completed, `release-evidence-app-deploy-*` records the expected service, image tag, and task definition, and `make post-deploy-verify` or the incident bundle shows no unresolved alarm or verification failures.
3. Infra apply: confirm the selected `Infra Apply` run matches the reviewed `Infra Plan` for the current default-branch SHA, and the plan plus release evidence match the intended Terraform surface.
4. Rollback or drill: confirm the evidence timeline shows the failing revision, restored revision, relevant alarm window, and verification outcome.

## Common Commands

```bash
make infra-plan
make infra-apply
make app-deploy
make post-deploy-verify
make incident-evidence
make db-tunnel
make db-exec
make db-seed
```

Prefer downloaded `release-evidence-*` artifacts and the incident bundle over
ad hoc console review.

For workflow-specific recovery paths, use [Runbooks](runbooks/README.md).

## Access

RDS stays private. Use SSM port forwarding:

```bash
make db-tunnel
```

Local Grafana access:

```bash
make observability
```
