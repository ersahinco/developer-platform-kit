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
| `data-support-deploy.yml` | Manual `workflow_dispatch` with approved immutable `image_tag` and `confirm_data_support_deploy=deploy-data-support` on the default branch | promotes support job task-definition revisions for explicit data workloads; rollback category `support_task_image` | `release-evidence-data-support-deploy-*` artifact and step summary |
| `operational-snapshot.yml` | Manual `workflow_dispatch` with `confirm_snapshot=run-operational-snapshot` on the default branch | runs the promoted `operational_snapshot_job` task definition and captures its structured readiness event | `release-evidence-operational-snapshot-*` artifact and step summary |
| `data-runtime-switch.yml` | Manual `workflow_dispatch` with reviewed `switch_step` and `confirm_switch=switch-runtime` on the default branch | advances runtime mode through one guarded forward transition at a time | `release-evidence-data-runtime-switch-*` artifact and step summary |
| `data-schema-apply.yml` | Manual `workflow_dispatch` with approved immutable `image_tag`, reviewed `schema_phase`, and `confirm_schema_apply=apply-schema` on the default branch | runs reviewed Liquibase schema apply as an explicit data stage; contract phase additionally requires `confirm_contract_ready=contract-ready` and `READ_MODE=new` plus `WRITE_MODE=new` | `release-evidence-data-schema-apply-*` artifact and step summary |
| `data-backfill.yml` | Manual `workflow_dispatch` with approved immutable `image_tag` and `confirm_backfill=run-backfill` on the default branch | runs reviewed backfill after confirming runtime modes are in the dual-write stage | `release-evidence-data-backfill-*` artifact and step summary |
| `infra-plan.yml` | pull request, main push, or manual run | produces reviewed Terraform plans without changing cloud resources | uploaded Terraform plan artifact and optional PR comment |
| `infra-apply.yml` | Manual `workflow_dispatch` with successful `plan_run_id` and `confirm_apply=apply` on the default branch | applies only reviewed Terraform plan artifacts for the current default-branch SHA | `release-evidence-infra-apply-*` artifact and step summary |

Rule: PRs prove correctness. Manual workflows promote a reviewed artifact or
reviewed plan. Every cloud-changing step leaves portable evidence.

## Pipeline Shape

The delivery toolkit provides a complete, opinionated GitHub Actions delivery
shape without hiding GitHub Actions. Keep the lanes generic and evidence-first
so another app repo can copy them directly today, and so repeated adoption can
promote them later into reusable workflows or a GitHub template:

1. App lane: build once, test, lint, scan, publish immutable image, record image
   digest and build evidence.
2. Infra lane: plan, policy-check, review, apply only the reviewed plan, record
   plan/apply evidence.
3. Data lane: expand schema, dual-write, backfill, switch reads, switch writes,
   contract cleanup, record runtime modes and job evidence.
4. Runtime lane: deploy immutable image, observe rollout, verify health,
   metrics, alarms, and integration checks.
5. Rollback lane: redeploy a known-good image, restore reviewed runtime modes,
   or rerun/stop bounded jobs; do not mutate unrelated infra during app
   rollback.

The current asset is the lane shape plus working workflows in this repo, not a
separate reusable-workflow package. The contract stays the same when extraction
is justified: explicit inputs, least privilege, pinned actions, no
cloud-changing side effects in validation jobs, and release evidence that names
workload, run ID, revision, artifact, verification result, and rollback
category.

## GitHub Setup

GitHub environment: `aws`

Required environment secret for reviewed deploy, apply, and operator jobs:

- `AWS_ROLE_ARN`

Required repository variable for default-branch infrastructure plans:

- `AWS_ROLE_ARN` - use the `infra/platform` `github_actions_role_arn` output

Useful repository variables:

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
- `AWS_REGION` and `STACK_NAME` exported for the target runtime

Create the primary edge token secret out of band:

```bash
aws secretsmanager create-secret \
  --name "${STACK_NAME}/edge-token" \
  --region "${AWS_REGION}" \
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
the `aws-ecs` admitted list in `platform/workload-runtime-support.json`:

1. The workload already passes local proof through tests and `make runtime-conformance`.
2. `platform/workloads.json` declares portable owner and config names; the runtime-support inventory records AWS admission.
3. `infra/app/` realizes only the needed ECS, database, messaging, storage, DNS, or scheduler surfaces.
4. The app lifecycle stays build once, promote immutable image, verify, and roll back by image.
5. Infra lifecycle stays reviewed plan then reviewed apply; no app deploy step repairs infra shape.
6. Data lifecycle stays explicit: expand, dual-write, backfill, switch, contract.

Rule: do not admit a workload to AWS just because it exists under `apps/`.

## Review Loop

Use [Operator Day 2 Commands](operator-day-2.md) as the short command sheet.
The same evidence-download and incident-evidence loop applies to deploys and
applies; keep the exact commands there so the operator path has one owner.

Checks:

1. App build: confirm branch, SHA, immutable `sha-...` image tag, and expected `release-evidence-app-build-*` artifacts.
2. App deploy: confirm `release-evidence-app-deploy-*` records the expected service, image tag, task definition, and rollout timing, and `make post-deploy-verify` or the incident bundle shows no unresolved alarm or verification failures.
3. Data or operator workflow: confirm the matching `release-evidence-data-*` or `release-evidence-operational-snapshot-*` artifact records the intended image tag, task definition, and stage-specific preconditions or outputs.
4. Infra apply: confirm the selected `Infra Apply` run matches the reviewed `Infra Plan` for the current default-branch SHA, and the plan plus release evidence match the intended Terraform surface.
5. Rollback: redeploy a known-good immutable image tag or restore the reviewed runtime mode, then confirm verification and alarm state.

Operator workflows also upload an `operator-payload-*` artifact with the
structured terminal job event as `operator-event.json` and an operator-readable
`operator-event.md` summary. Download it through
[Operator Day 2 Commands](operator-day-2.md#operator-jobs).

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
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw primary_edge_service_name)" \
  --region "$AWS_REGION" \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount,deployments:deployments[*].{status:status,rolloutState:rolloutState,reason:rolloutStateReason,taskDefinition:taskDefinition,desired:desiredCount,running:runningCount,pending:pendingCount,failed:failedTasks},events:events[:10]}'
```

For the primary edge service, inspect target health if ECS says tasks are
running but the service is not stable:

```bash
target_group_arn=$(aws ecs describe-services \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw primary_edge_service_name)" \
  --region "$AWS_REGION" \
  --query 'services[0].loadBalancers[0].targetGroupArn' \
  --output text)
aws elbv2 describe-target-health --target-group-arn "$target_group_arn"
```

For container start failures, look at the recent stopped tasks and logs:

```bash
aws ecs list-tasks \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --service-name "$(terraform -chdir=infra/app output -raw primary_edge_service_name)" \
  --desired-status STOPPED \
  --max-items 5 \
  --region "$AWS_REGION"

aws logs describe-log-streams \
  --log-group-name "/ecs/${STACK_NAME}/$(terraform -chdir=infra/app output -raw primary_edge_service_name)" \
  --order-by LastEventTime \
  --descending \
  --max-items 5 \
  --region "$AWS_REGION"
```

If the failed deploy came from GitHub Actions, download the release evidence
and build an incident bundle through
[Operator Day 2 Commands](operator-day-2.md#incident-evidence) before changing
state.

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

Before dispatching cloud-changing workflows, start with
[Operator Day 2 Commands](operator-day-2.md), then run the local
dry-readiness gate:

```bash
make platform-doctor-cloud
make platform-toolkit-validate-cloud
make workflow-dry-run-commands
```

It does not call AWS mutating APIs. It checks workstation/cloud operator
readiness, runs local security checks, lints GitHub workflow shape, checks
platform policy, and runs the contract/script tests that prove workflows,
Terraform helpers, task-definition rendering, post-deploy verification, release
evidence, and incident evidence still derive from the platform contract where
appropriate.

Run `make workload-readiness-cloud` first when you need the per-workload cloud
view: AWS admission, policy/delivery gate, structured log contract, secret
injection proof, delivery workflow, evidence artifact, log group, and rollback
proof category.

`make platform-toolkit-validate-cloud` includes `make security-readiness`,
`make infra-validate-local`, and local workflow dry-run validation.
`security-readiness` runs `make secret-scan` and `make dependency-audit`.
`infra-validate-local` mirrors the Terraform parse/validate portion of
`infra-plan.yml` without remote backend initialization or cloud mutation. It
can still download provider plugins through Terraform if they are not already
cached. If provider initialization reaches AWS credential checks, the target
prints an actionable readiness message instead of treating an expired or
missing token as a Terraform syntax failure.

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
local workflow files and confirms dry-run-capable workflows guard mutation and
release-evidence steps. Use `make workflow-dry-run-validate-gh` when you also
want to confirm GitHub CLI authentication and list the remote workflows before
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
