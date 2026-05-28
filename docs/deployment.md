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
6. Run `data-backfill.yml` only after dual-write is active and the change needs a backfill stage.
7. Advance runtime mode with `data-runtime-switch.yml` from `READ_MODE=legacy` to `READ_MODE=new`.
8. Advance runtime mode with `data-runtime-switch.yml` from `WRITE_MODE=dual` to `WRITE_MODE=new`.
9. Run a reviewed contract-phase schema apply only after app reads and writes no longer depend on the old shape.

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
2. App deploy: confirm `release-evidence-app-deploy-*` records the expected service, image tag, and task definition, and `make post-deploy-verify` or the incident bundle shows no unresolved alarm or verification failures.
3. Data workflow: confirm the matching `release-evidence-data-*` artifact records the intended image tag, task definition, and stage-specific preconditions or outputs.
4. Infra apply: confirm the selected `Infra Apply` run matches the reviewed `Infra Plan` for the current default-branch SHA, and the plan plus release evidence match the intended Terraform surface.
5. Rollback: redeploy a known-good immutable image tag or restore the reviewed runtime mode, then confirm verification and alarm state.

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
```

It does not call AWS mutating APIs. It lints GitHub workflow shape, checks
platform policy, and runs the contract/script tests that prove workflows,
Terraform helpers, task-definition rendering, post-deploy verification, release
evidence, and incident evidence still derive from the platform contract where
appropriate.

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
