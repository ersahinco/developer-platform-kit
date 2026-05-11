# App And Infra Ownership Boundary

Use this boundary when reviewing deploys, rollback drills, and Terraform plans.
The goal is boring ownership: fast app iteration through GitHub Actions, infra
rollback through Terraform, and data-phase rollback through controlled runtime
configuration.

## Ownership Model

| Surface | Owner | Normal rollback path |
|---|---|---|
| ECS cluster, ECS service shape, deployment circuit breaker, deployment alarms, ALB, target groups, security groups, IAM, log groups, ECR repositories, S3 buckets, queues, schedules | Terraform via `Infra Plan` and `Infra Apply` | Revert the infra commit, review the new plan, then apply the reviewed revert plan. |
| App image tag and app ECS task-definition revision after bootstrap | GitHub Actions `App Deploy` and `App No-Data Rollback Drill` | ECS native rollback to the last completed deployment, observed by the workflow. |
| One-off support task-definition revisions for Liquibase, worker, data export, and consumer images | GitHub Actions `App Deploy` | Re-register known-good task definitions or rerun the previous app deploy image. |
| Runtime data-phase switches, currently `READ_MODE` and `WRITE_MODE` in `app_runtime_config` | Admin API and `Data Runtime Rollback Drill` | Restore the captured runtime config value; no Terraform apply and no schema change. |
| Database schema, migration history, and seeded runtime defaults | Liquibase | Additive forward fix before contract; snapshot/restore only after destructive contract changes. |

Short version: Terraform owns ECS service guardrails, and GitHub Actions owns app task-definition revisions after bootstrap.

## Current Terraform Caveat

`ignore_task_definition_changes = true` on the ECS service prevents Terraform
from moving the running service back to an older task definition. It does not
stop the upstream ECS module from planning a replacement of its managed
bootstrap `aws_ecs_task_definition` resource when container definitions drift
from the app pipeline.

That means a routine infra apply can still cross the app deploy boundary by
registering a stale or different task-definition revision. `Infra Apply` blocks
that by running:

```bash
scripts/ci/ci_guard_infra_plan_blast_radius.sh infra/app/app_plan_output.txt
```

If the reviewed app plan includes `aws_ecs_task_definition` changes, apply fails
unless the operator explicitly sets:

```text
allow_ecs_task_definition_changes=allow-ecs-task-definition-changes
```

Use that override only for a reviewed intentional task-definition infra change.
For normal app image rollback, use ECS native rollback or the app deploy path.

## Clean Infra Rollback Drill Criteria

A clean infra rollback drill changes only a Terraform-owned surface and keeps
the app and data ownership boundaries untouched.

Before applying, the reviewed plan must show:

- The intended reversible infra or observability change.
- No `aws_ecs_task_definition` replacement unless that is the reviewed target.
- No ECS service replacement or service move to an older app image.
- No RDS replacement, S3 bucket deletion, queue replacement, Liquibase task,
  backfill task, data export, or runtime-mode change.

When the plan is clean, run the normal infra path: apply the forward plan,
observe the changed surface, revert the commit, review the revert plan, and
apply the revert plan.

## Future Migration Option

A stricter future model would remove the app task-definition resource from the
Terraform-managed ECS service after bootstrap and have Terraform reference an
externally managed task-definition ARN. Do that only as its own reviewed
migration because it changes Terraform state ownership and can deregister or
replace resources if handled casually.
