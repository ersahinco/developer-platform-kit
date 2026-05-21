# AWS Catalog Extraction Map

This file documents which AWS pieces are good catalog candidates and which
should stay in the current assembly roots for now.

The goal is not to maximize module count. The goal is to extract only the
infrastructure slices that are stable enough to reuse without hiding standard
Terraform or AWS concepts.

This is the extraction map for the current AWS runtime target. Future runtime
targets should follow the same pattern under `infra/catalog/<runtime-target>/`
rather than changing the stable-center workload contract.

## Current Candidates

| Candidate | Current owner | Extract when |
|---|---|---|
| VPC baseline | `infra/platform/network.tf` | Another stack needs the same VPC/endpoints shape with only parameter changes |
| ECR repository baseline | `infra/app/ecr.tf` | A second runtime or stack needs the same immutable image repository pattern |
| ECS cluster baseline | `infra/app/compute_ecs.tf` | Another workload group needs the same cluster/service defaults |
| App/service log groups | `infra/app/app_log_groups.tf`, `infra/app/workload_jobs.tf` | Log-group retention/KMS patterns repeat outside the current stack |
| RDS PostgreSQL baseline | `infra/app/database.tf` | Another bounded data service needs the same private Postgres posture |
| ALB edge baseline | `infra/app/edge.tf`, `infra/app/edge_access_logs.tf` | Another public edge needs the same TLS/WAF/logging/target alarm pattern |
| Dapr broker backing resources | `infra/app/messaging.tf` | Another Dapr-backed workload needs the same SNS/SQS runtime pattern |
| Scheduled Fargate job baseline | `infra/app/workload_jobs.tf` | A second recurring ECS task needs the same scheduler/task-role pattern |
| Data hub bucket baseline | `infra/app/object_storage.tf` | Another workload needs the same controlled object-output shape |

## Keep In Assembly Roots

These should remain in `infra/platform` or `infra/app` until a second use case
proves they are really reusable:

- one-off schema rollout wiring
- current app-specific runtime mode/admin behavior
- release-drill-specific alarm thresholds
- one-stack naming and ownership conventions
- support task registration choreography handled by workflows

## Extraction Rules

- Extract only after a second real consumer or a clearly repeated platform
  pattern appears.
- Prefer modules that expose normal AWS/Terraform concepts, not private DSL
  wrappers.
- Keep lifecycle boundaries intact: bootstrap/platform modules stay separate
  from runtime/app modules.
- Keep workload meaning in `platform/workloads.json` and `platform/concerns/`;
  catalog extraction should not become a second contract surface.
- If extraction would obscure the repo’s teaching value, leave the code in the
  assembly root and document the candidate here instead.
