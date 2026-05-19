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

## GitHub Change Control Matrix

These workflows intentionally separate review from cloud change. The common path
is: validate and plan on pull requests, then manually promote reviewed artifacts
or reviewed plans on the default branch.

| Workflow | Trigger and reviewed input | Control boundary | Evidence |
|---|---|---|---|
| `app-build.yml` | Manual `workflow_dispatch` with `confirm_build=build` after PR review on the default branch | Builds, scans, attests, and pushes immutable images only; no runtime rollout | Build summary plus `release-evidence-app-build-*` artifact per image |
| `app-deploy.yml` | Manual `workflow_dispatch` with approved immutable `image_tag` and `confirm_deploy=deploy` on the default branch | Runs Liquibase, updates ECS services and support task definitions, verifies health, and runs backfill if needed | `release-evidence-app-deploy-*` artifact and step summary |
| `infra-plan.yml` | Pull request, main push, or manual run | Produces reviewed Terraform plans without changing cloud resources | Uploaded Terraform plan artifact and optional PR comment |
| `infra-apply.yml` | Manual `workflow_dispatch` with successful `plan_run_id` and `confirm_apply=apply` on the default branch | Applies only reviewed Terraform plan artifacts for the current default-branch SHA | `release-evidence-infra-apply-*` artifact and step summary |

The practical rule is simple: PRs prove correctness, manual workflows promote a
reviewed artifact or reviewed plan, and every cloud-changing step leaves behind
portable evidence.

## Review Checklist

Use the same short review loop for deploys, applies, and drills:

```bash
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id> \
make incident-evidence
```

Then check the evidence for the path you are reviewing:

1. App build review:
   Confirm the selected `App Build` run is on the expected branch and SHA, the image tag is the intended immutable `sha-...` tag, and the downloaded `release-evidence-app-build-*` artifacts cover the images you expect to deploy.
2. App deploy review:
   Confirm Liquibase and deploy both completed, `release-evidence-app-deploy-*` records the expected service, image tag, and task definition, and `make post-deploy-verify` or the incident bundle does not show unresolved alarm or verification failures.
3. Infra apply review:
   Confirm the selected `Infra Apply` run corresponds to the reviewed `Infra Plan` for the current default-branch SHA, and the release evidence plus plan artifact reflect only the intended Terraform change surface.
4. Rollback or drill review:
   Confirm the evidence timeline shows the failing revision, the restored revision, the relevant alarm window, and the verification outcome before declaring the drill or rollback successful.

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

For deploy or apply review, prefer downloaded `release-evidence-*` artifacts and
the incident bundle over ad hoc console spelunking. Point the bundle command at
the downloaded artifacts when you want one portable view that combines release
events with current alarms, ECS state, and query hints:

```bash
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id> \
make incident-evidence
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
