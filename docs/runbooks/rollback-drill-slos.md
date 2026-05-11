# Rollback Drill SLOs

Use these SLOs to judge the DevOps pipeline itself. They are not product
availability SLOs. They answer a narrower question: when a controlled app,
infra, or data rollout goes wrong, can the pipeline detect it, restore the last
known-good state, and produce evidence quickly enough to keep iteration safe?

## Objectives

| Drill | Trigger | SLO | Evidence |
|---|---|---:|---|
| App rollback, error mode | `/ready` returns 503 and trips the ALB target 5xx deployment alarm. | ECS automatic rollback observed within 10 min; restored app verification within 2 min. | `App No-Data Rollback Drill` summary, ECS service events, 5xx alarm history, `verify_post_deploy.py`. |
| App rollback, latency mode | `/ready` delays 3s and trips the ALB p95 latency deployment alarm. | ECS automatic rollback observed within 15 min; restored app verification within 2 min. | `App No-Data Rollback Drill` summary, ECS service events, latency alarm history, `verify_post_deploy.py`. |
| Infra no-data rollback | A reversible Terraform-only change is applied and then reverted. | Reviewed plan in <= 5 min, apply in <= 15 min, revert plan+apply in <= 30 min. | `Infra Plan` and `Infra Apply` run IDs, reviewed no-data plan, restored resource state. |
| Runtime data-phase rollback | `WRITE_MODE` is moved from `legacy` to `dual` and back to the captured safe phase. | API write-mode rollback verified within 2 min; restored app verification within 2 min. | `Data Runtime Rollback Drill` summary, admin API response, 5s runtime-config cache expiry, `verify_post_deploy.py`. |
| Backfill/data job containment | A resumable job fails before runtime cutover. | Stop or rerun decision within 10 min; no read-mode advancement until reconciliation passes. | Worker logs, checkpoint state, reconciliation output, unchanged runtime modes. |

## Current Baseline

The current app drill baseline was established on 2026-05-10 in
`eu-central-1`:

| Drill | GitHub Actions run | Observed result |
|---|---|---:|
| App latency rollback | `25627263917` | Passed in 10m19s. |
| App error rollback | `25627680472` | Passed in 6m32s. |
| Runtime data-phase rollback | `25675925524` | Passed. `WRITE_MODE` rollback observed in 2s; restored verification passed in 8s. |
| Infra apply for rollback support | `25626714215` | Passed in 51s. |
| Infra no-data rollback preflight | `25676047073` | Stopped before apply. Plan completed in 2m37s but included unrelated app ECS task-definition replacement. |

Treat a single SLO breach as a pipeline regression to investigate. Treat two
consecutive breaches of the same drill as a release-blocking issue until the
signal, timeout, rollback, or verification path is repaired.

## Required Guardrails

- App rollback drills must not run Liquibase, backfill, data export, or runtime
  mode changes.
- Infra rollback drills must not include RDS replacement, S3 object deletion,
  queue replacement, or data hub changes.
- Data-phase rollback must stay additive until the contract phase. After a
  destructive contract migration, rollback is snapshot/restore work, not a fast
  pipeline rollback.
- Grafana/Prometheus/Loki are the human observation layer. ECS automatic
  rollback for the app drill is driven by CloudWatch deployment alarms because
  ECS deployment alarms are CloudWatch-native.

## Review Cadence

Run both app rollback modes after changes to any of these surfaces:

- ECS service deployment configuration.
- ALB health, 5xx, or latency alarms.
- App readiness, health, metrics, or middleware.
- App deploy or rollback GitHub Actions workflows.

Run the infra rollback drill after changes to:

- Terraform workflow permissions.
- Terraform state, module, or provider versions.
- Observability resources that operators rely on during rollback.

Run data-phase rollback tests before any release that advances `READ_MODE`,
`WRITE_MODE`, backfill behavior, or contract migration readiness.

## Workflow Inventory

The rollback drill workflows are intentionally split by ownership boundary:

- `App No-Data Rollback Drill` exercises app task-definition rollback only.
- `Data Runtime Rollback Drill` exercises runtime data-phase rollback only.
- Infra rollback drills use reviewed `Infra Plan` and `Infra Apply` runs; one-off
  state migration workflows, such as app task-definition ownership migration,
  are not rollback drills and should stay separately reviewed.

## Infra Drill Preflight

Before running `Infra Apply`, inspect the reviewed `Infra Plan` artifact. Apply
only when the plan contains the intended infra drill target and no unrelated
replacement.

Stop and revert the drill commit if the plan includes:

- `aws_ecs_task_definition` replacement outside the drill target.
- ECS service replacement or task definition rollback to an older app image.
- RDS, S3 bucket, SQS, SNS, Liquibase, backfill, data export, or runtime-mode
  changes.

The 2026-05-11 infra preflight run `25676047073` correctly stopped before
apply because the plan included the intended CloudWatch alarm description
update plus an unrelated app task-definition replacement from app-deploy
ownership drift. The ownership boundary is documented in
[App And Infra Ownership Boundary](app-infra-ownership.md).

`Infra Apply` has a blast-radius guard for future accidental drift. If the
reviewed app plan contains ECS task-definition create, replace, or destroy
changes, the apply fails unless the operator explicitly sets:

```text
allow_ecs_task_definition_changes=allow-ecs-task-definition-changes
```

## Runtime Config Drill

Use `Data Runtime Rollback Drill` as the safe, representative data rollback
exercise. It intentionally mutates only `app_runtime_config`; it does not run
Liquibase, backfill, data export, seed scripts, or order writes.

The drill currently requires `READ_MODE=legacy` and `WRITE_MODE=legacy`, moves
`WRITE_MODE` to `dual`, then rolls it back to the captured previous value. An
always-run restore step posts the captured value again if any earlier step
fails.

Run it from the default branch:

```bash
gh workflow run "Data Runtime Rollback Drill" \
  --ref main \
  -f confirm_drill=data-rollback-drill
```
