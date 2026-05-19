# Rollback Drill SLOs

Use these SLOs to judge the delivery pipeline itself, not product availability.
They answer a narrow question: when a controlled rollout goes wrong, can the
toolkit restore a known-good state quickly enough to keep iteration safe?

## Objectives

| Drill | Trigger | SLO | Evidence |
|---|---|---:|---|
| App rollback, error mode | `/ready` returns 503 and trips the ALB target 5xx deployment alarm. | ECS automatic rollback observed within 10 min; restored app verification within 2 min. | `App No-Data Rollback Drill` summary, ECS service events, 5xx alarm history, `verify_post_deploy.py`. |
| App rollback, latency mode | `/ready` delays 3s and trips the ALB p95 latency deployment alarm. | ECS automatic rollback observed within 15 min; restored app verification within 2 min. | `App No-Data Rollback Drill` summary, ECS service events, latency alarm history, `verify_post_deploy.py`. |
| Infra no-data rollback | A reversible Terraform-only change is applied and then reverted. | Reviewed plan in <= 5 min, apply in <= 15 min, revert plan+apply in <= 30 min. | `Infra Plan` and `Infra Apply` run IDs, reviewed no-data plan, restored resource state. |
| Runtime data-phase rollback | `WRITE_MODE` is moved from `legacy` to `dual` and back to the captured safe phase. | API write-mode rollback verified within 2 min; restored app verification within 2 min. | `Data Runtime Rollback Drill` summary, admin API response, 5s runtime-config cache expiry, `verify_post_deploy.py`. |

Each cloud-changing apply/deploy/drill path also uploads a release evidence
artifact with Markdown, JSON, and JSONL forms. Treat that artifact as the
portable timeline record that can later be pushed into Loki for Grafana
correlation.

## Evidence Review Path

Use the same review path for both rollback drills and real rollback analysis:

```bash
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id> \
make incident-evidence
```

For a drill, confirm the bundle lines up the triggering fault mode, the alarm
or runtime-mode transition, the restored revision or phase, and the final
verification outcome before marking the drill complete.

Treat a single SLO breach as a pipeline regression to investigate. Treat two
consecutive breaches of the same drill as release-blocking until the signal,
timeout, rollback, or verification path is repaired.

## Required Guardrails

- App rollback drills must not run Liquibase, backfill, data export, or runtime
  mode changes.
- Infra rollback drills must not include RDS replacement, S3 object deletion,
  queue replacement, or data hub changes.
- Data-phase rollback must stay additive until the contract phase. After a
  destructive contract migration, rollback is snapshot/restore work, not a fast
  pipeline rollback.
- Backfill/data job containment is a guardrail, not a separate rollback drill:
  if a resumable job fails before runtime cutover, stop or rerun within 10
  minutes and do not advance read mode until reconciliation passes.
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
- Infra rollback drills use reviewed `Infra Plan` and `Infra Apply` runs.

There are exactly two permanent rollback drill workflows. One-off migration
workflows must be removed after successful execution so they do not become
parallel rollback paths.

## Infra No-Data Drill

Use the normal Terraform path:

```text
infra-only change
  -> Infra Plan
  -> Infra Apply
  -> observe
  -> revert commit
  -> Infra Plan
  -> Infra Apply
  -> verify restored state
```

Choose one small reversible infra or observability change. Good targets are:

- Grafana dashboard JSON
- Prometheus alert threshold or label
- CloudWatch app symptom alarm threshold
- ECS desired count for non-production drill windows

Do not use schema changes, RDS changes, queue replacement, object deletion, or
runtime `READ_MODE`/`WRITE_MODE` changes for this drill.

Path:

1. Create one small reversible infra or observability change.
2. Review `Infra Plan`.
3. Merge to the default branch.
4. Run `Infra Apply` with the reviewed plan run id.
5. Observe the changed surface.
6. Revert the commit.
7. Repeat the same reviewed plan/apply path for the revert.

Apply only when the reviewed plan stays inside Terraform-owned surfaces and
does not pull in app task-definition drift, data changes, or destructive
replacement. The ownership boundary is in
[App And Infra Ownership Boundary](app-infra-ownership.md).

Stop and do not apply if the plan includes:

- RDS replacement or unrelated modification
- S3 bucket deletion, lifecycle tightening, or object deletion
- SQS/SNS replacement
- ECS task or service replacement outside the intended target
- app `aws_ecs_task_definition` changes crossing the app deploy boundary
- Liquibase, data export, backfill, or runtime-mode actions

Verify after rollback:

- the changed surface matches the previous version
- `make observability-delivery-verify` still passes when relevant
- no data hub objects were created or deleted
- no Liquibase, backfill, data-export, or runtime-mode workflow was run
