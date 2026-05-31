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
| `app-deploy.yml` | Manual `workflow_dispatch` with approved immutable `image_tag` and `confirm_deploy=deploy` on the default branch | updates ECS service revisions and verifies runtime health only | `release-evidence-app-deploy-*` artifact and step summary |
| `data-support-deploy.yml` | Manual `workflow_dispatch` with approved immutable `image_tag` and `confirm_data_support_deploy=deploy-data-support` on the default branch | promotes support job task-definition revisions for explicit data workloads | `release-evidence-data-support-deploy-*` artifact and step summary |
| `operational-snapshot.yml` | Manual `workflow_dispatch` with `confirm_snapshot=run-operational-snapshot` on the default branch | runs the promoted `operational_snapshot_job` task definition and captures its structured readiness event | `release-evidence-operational-snapshot-*` artifact and step summary |
| `data-runtime-switch.yml` | Manual `workflow_dispatch` with reviewed `switch_step` and `confirm_switch=switch-runtime` on the default branch | advances runtime mode through one guarded forward transition at a time | `release-evidence-data-runtime-switch-*` artifact and step summary |
| `data-schema-apply.yml` | Manual `workflow_dispatch` with approved immutable `image_tag`, reviewed `schema_phase`, and `confirm_schema_apply=apply-schema` on the default branch | runs reviewed Liquibase schema apply as an explicit data stage; contract phase additionally requires `confirm_contract_ready=contract-ready` and `READ_MODE=new` plus `WRITE_MODE=new` | `release-evidence-data-schema-apply-*` artifact and step summary |
| `data-backfill.yml` | Manual `workflow_dispatch` with approved immutable `image_tag` and `confirm_backfill=run-backfill` on the default branch | runs reviewed backfill after confirming runtime modes are in the dual-write stage | `release-evidence-data-backfill-*` artifact and step summary |
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

Create the primary edge token secret out of band:

```bash
aws secretsmanager create-secret \
  --name "${STACK_NAME:-aws-sdlc-containers}/edge-token" \
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

1. Build and push immutable images with `app-build.yml`.
2. Run `data-schema-apply.yml` only when the release needs an explicit schema stage.
3. Roll out service images with `app-deploy.yml`.
4. Advance runtime mode with `data-runtime-switch.yml` from `legacy` to `dual` only when the app release is ready for dual-write.
5. Promote support-job image revisions with `data-support-deploy.yml` only for the specific workload that needs the new image.
6. Run `operational-snapshot.yml` when you need a point-in-time readiness snapshot for release or incident evidence.
7. Run `data-backfill.yml` only after dual-write is active and the change needs a backfill stage.
8. Advance runtime mode with `data-runtime-switch.yml` from `READ_MODE=legacy` to `READ_MODE=new`.
9. Advance runtime mode with `data-runtime-switch.yml` from `WRITE_MODE=dual` to `WRITE_MODE=new`.
10. Run a reviewed contract-phase schema apply only after app reads and writes no longer depend on the old shape.

The intended data path stays explicit:

1. `expand`: additive schema apply
2. `dual-write`: app release and guarded `write-legacy-to-dual`
3. `backfill`: explicit backfill workflow
4. `switch`: guarded `read-legacy-to-new`
5. `cutover`: guarded `write-dual-to-new`
6. `contract`: reviewed cleanup schema apply

Because schema and backfill are no longer side effects of `app-deploy.yml`,
app rollback stays image-based.

## Admitting A Local Workload To AWS

Use this checklist before changing a workload from local-first support to
`runtime.admitted: ["aws-ecs"]`:

1. The workload already passes local proof through tests and `make runtime-conformance`.
2. `platform/workloads.json` declares the workload `owner`, config names, and AWS admission intent explicitly.
3. `infra/app/` realizes only the needed ECS, database, messaging, storage, DNS, or scheduler surfaces.
4. The app lifecycle stays build once, promote immutable image, verify, and roll back by image.
5. Infra lifecycle stays reviewed plan then reviewed apply; no app deploy step repairs infra shape.
6. Data lifecycle stays explicit: expand, dual-write, backfill, switch, contract.

Rule: do not admit a workload to AWS just because it exists under `apps/`.

## Review Loop

Use the same loop for deploys and applies:

```bash
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id> \
make incident-evidence
```

Checks:

1. App build: confirm branch, SHA, immutable `sha-...` image tag, and expected `release-evidence-app-build-*` artifacts.
2. App deploy: confirm `release-evidence-app-deploy-*` records the expected service, image tag, task definition, and rollout timing, and `make post-deploy-verify` or the incident bundle shows no unresolved alarm or verification failures.
3. Data or operator workflow: confirm the matching `release-evidence-data-*` or `release-evidence-operational-snapshot-*` artifact records the intended image tag, task definition, and stage-specific preconditions or outputs.
4. Infra apply: confirm the selected `Infra Apply` run matches the reviewed `Infra Plan` for the current default-branch SHA, and the plan plus release evidence match the intended Terraform surface.
5. Rollback: redeploy a known-good immutable image tag or restore the reviewed runtime mode, then confirm verification and alarm state.

Operator workflows also upload an `operator-payload-*` artifact with the
structured terminal job event as `operator-event.json` and an operator-readable
`operator-event.md` summary:

```bash
GH_RUN_ID=<workflow-run-id> make operator-payload-download
```

## Slow ECS Deployments

`app-deploy.yml` observes each ECS service rollout after `update-service`.
The workflow log and step summary include:

- elapsed rollout time
- target task definition
- deployment status, desired/running/pending/failed task counts
- target-group health summary when the service has an ALB target group
- recent ECS service events

Use those events first. They usually show whether the deploy is waiting for
image pull, task start, target health, circuit breaker rollback, or capacity.

If the rollout is slow or stuck, collect the same context locally:

```bash
aws ecs describe-services \
  --cluster "${STACK_NAME:-aws-sdlc-containers}" \
  --services api \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount,deployments:deployments[*].{status:status,rolloutState:rolloutState,reason:rolloutStateReason,taskDefinition:taskDefinition,desired:desiredCount,running:runningCount,pending:pendingCount,failed:failedTasks},events:events[:10]}'
```

For the primary edge service, inspect target health if ECS says tasks are
running but the service is not stable:

```bash
target_group_arn=$(aws ecs describe-services \
  --cluster "${STACK_NAME:-aws-sdlc-containers}" \
  --services api \
  --query 'services[0].loadBalancers[0].targetGroupArn' \
  --output text)
aws elbv2 describe-target-health --target-group-arn "$target_group_arn"
```

For container start failures, look at the recent stopped tasks and logs:

```bash
aws ecs list-tasks \
  --cluster "${STACK_NAME:-aws-sdlc-containers}" \
  --service-name api \
  --desired-status STOPPED \
  --max-items 5

aws logs describe-log-streams \
  --log-group-name "/ecs/${STACK_NAME:-aws-sdlc-containers}/api" \
  --order-by LastEventTime \
  --descending \
  --max-items 5
```

If the failed deploy came from GitHub Actions, download the release evidence
and build an incident bundle before changing state:

```bash
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id> \
make incident-evidence
```

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

## Safe Cloud Readiness

Before dispatching cloud-changing workflows, run the local dry-readiness gate:

```bash
make platform-toolkit-validate-cloud
make infra-validate-local
make workflow-dry-run-validate
make workflow-dry-run-commands
```

It does not call AWS mutating APIs. It lints GitHub workflow shape, checks
platform policy, and runs the contract/script tests that prove workflows,
Terraform helpers, task-definition rendering, post-deploy verification, release
evidence, and incident evidence still derive from the platform contract where
appropriate.

`make infra-validate-local` mirrors the Terraform parse/validate portion of
`infra-plan.yml` without remote backend initialization or cloud mutation. It can
still download provider plugins through Terraform if they are not already
cached. If provider initialization reaches AWS credential checks, the target
prints an actionable readiness message instead of treating an expired or missing
token as a Terraform syntax failure.

`make workflow-dry-run-commands` prints copy-ready `gh workflow run` commands
for each non-destructive workflow dry run, including the app-build validation
path that skips image build and push unless `confirm_build=build`. Set
`IMAGE_TAG` to a tag from a successful app-build run for the image-based
dry-runs; those dry-runs validate ECR image availability. Override the other
defaults when needed:

```bash
IMAGE_TAG=sha-<commit> \
TARGET_WORKLOAD=backfill_worker \
SCHEMA_PHASE=expand \
SWITCH_STEP=auto-detect \
PLAN_RUN_ID=<infra-plan-run-id> \
make workflow-dry-run-commands
```

`make workflow-dry-run-validate` checks the generated command inputs against the
local workflow files. Use `make workflow-dry-run-validate-gh` when you also want
to confirm GitHub CLI authentication and list the remote workflows before
dispatch.

The dry-run dispatches still run inside the `aws` GitHub environment and may
run the app-build validation job, read AWS state, validate image tags, inspect
current runtime mode, render task definitions, or resolve a reviewed plan. They
skip the mutation steps: image build/push, service updates, task-definition
registration, one-off task execution, runtime-mode writes, Terraform apply, and
release-evidence emission.

## Runtime Mode Switches

Use one forward transition at a time:

| Current state | Reviewed switch step | Target state |
|---|---|---|
| `READ_MODE=legacy`, `WRITE_MODE=legacy` | `write-legacy-to-dual` | `READ_MODE=legacy`, `WRITE_MODE=dual` |
| `READ_MODE=legacy`, `WRITE_MODE=dual` | `read-legacy-to-new` | `READ_MODE=new`, `WRITE_MODE=dual` |
| `READ_MODE=new`, `WRITE_MODE=dual` | `write-dual-to-new` | `READ_MODE=new`, `WRITE_MODE=new` |

`auto-detect` is for dry-run planning only. Use the explicit reviewed step for
the workflow that changes runtime mode.

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
