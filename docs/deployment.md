# Deployment

Current AWS delivery and operator flow.

Use [Platform Contract](platform-contract.md) for portable workload rules and
[Architecture](architecture.md) for repo ownership boundaries.

## Scope

- `infra/platform`: shared platform bootstrap, network, GitHub OIDC
- `infra/app`: RDS, ECS, ALB edge, jobs, messaging, storage, alarms
- GitHub Actions: image build, rollout, verification, release evidence

Safe rollout comes from additive schema change, runtime switches, and one-off
tasks, not from duplicating infrastructure.

## GitHub Change Control Matrix

| Workflow | Trigger and reviewed input | Control boundary | Evidence |
|---|---|---|---|
| `app-build.yml` | Manual `workflow_dispatch` with `confirm_build=build` after PR review on the default branch | Builds, scans, attests, and pushes immutable images only; no runtime rollout | Build summary plus `release-evidence-app-build-*` artifact per image |
| `app-deploy.yml` | Manual `workflow_dispatch` with approved immutable `image_tag` and `confirm_deploy=deploy` on the default branch | Runs Liquibase, updates ECS services and support task definitions, verifies health, and runs backfill if needed | `release-evidence-app-deploy-*` artifact and step summary |
| `infra-plan.yml` | Pull request, main push, or manual run | Produces reviewed Terraform plans without changing cloud resources | Uploaded Terraform plan artifact and optional PR comment |
| `infra-apply.yml` | Manual `workflow_dispatch` with successful `plan_run_id` and `confirm_apply=apply` on the default branch | Applies only reviewed Terraform plan artifacts for the current default-branch SHA | `release-evidence-infra-apply-*` artifact and step summary |

Rule: PRs prove correctness. manual workflows promote a reviewed artifact or reviewed plan. Every cloud-changing step leaves portable evidence.

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

## Review Checklist

Use the same review loop for deploys, applies, and drills:

```bash
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id> \
make incident-evidence
```

Checks by path:

1. App build review: confirm the selected `App Build` run is on the expected branch and SHA, the image tag is the intended immutable `sha-...` tag, and the downloaded `release-evidence-app-build-*` artifacts cover the images you expect to deploy.
2. App deploy review: confirm Liquibase and deploy both completed, `release-evidence-app-deploy-*` records the expected service, image tag, and task definition, and `make post-deploy-verify` or the incident bundle does not show unresolved alarm or verification failures.
3. Infra apply review: confirm the selected `Infra Apply` run corresponds to the reviewed `Infra Plan` for the current default-branch SHA, and the release evidence plus plan artifact reflect only the intended Terraform change surface.
4. Rollback or drill review: confirm the evidence timeline shows the failing revision, the restored revision, the relevant alarm window, and the verification outcome before declaring the drill or rollback successful.

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

For workflow-specific recovery paths, continue with
[Runbooks](runbooks/README.md).

## Access Patterns

RDS stays private. Use SSM port forwarding:

```bash
make db-tunnel
```

Local Grafana access:

```bash
make observability
```
