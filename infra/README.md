# Infrastructure Root

This directory is the single Terraform root for the shared ECS delivery stack.
Keep it as one root until a real lifecycle boundary appears. The current goal
is a readable, reviewable stack that demonstrates ECS delivery, safe database
rollout, and operator workflows without multiplying state files.

## Current Contract

- One AWS account and region for the reference stack.
- One S3-backed Terraform state key: `aws-sdlc-containers/stack.tfstate`.
- One VPC, ECS cluster, app service, RDS database, ALB, and Route 53 entrypoint.
- One S3 data hub bucket with raw, curated, and manifest prefix conventions.
- CI owns image promotion and task definition revisions after bootstrap.
- Terraform owns durable infrastructure and intentionally ignores app image
  task definition drift after CI deploys.

## File Map

| File | Concern |
|---|---|
| `versions.tf` | Terraform version, provider constraints, and S3 backend. |
| `providers.tf` | AWS provider, lookup data sources, locals, tags, and API token lookup. |
| `variables.tf` | Stack inputs and documented defaults. |
| `outputs.tf` | Operator-facing stack outputs. |
| `stack.tfvars` | Current shared-stack values. |
| `base_network_vpc.tf` | VPC and subnet tiers. |
| `base_edge.tf` | ALB, security groups, ACM, Route 53, and listener auth. |
| `base_data_rds.tf` | RDS Postgres and database security group. |
| `base_data_hub_s3.tf` | S3 data hub bucket and raw/curated/manifest prefix convention. |
| `base_compute_ecs.tf` | ECR repositories, ECS cluster, app service, and PgBouncer sidecar. |
| `support_jobs.tf` | One-off Liquibase and worker task definitions. |
| `identity.tf` | ECS task execution/runtime IAM. |
| `oidc_github_actions.tf` | Base GitHub Actions OIDC role and policies. |
| `optional_*.tf` | Explicit optional extensions that are not part of the minimum base path. |
| `oidc_optional_features.tf` | GitHub Actions IAM needed by optional extensions. |

## Module Policy

Use community modules for standard platform resources when they fit:

| Resource | Current implementation |
|---|---|
| VPC | `terraform-aws-modules/vpc/aws ~> 6.0` |
| ECS | `terraform-aws-modules/ecs/aws ~> 7.0` |
| RDS | `terraform-aws-modules/rds/aws ~> 7.0` |
| ECR | `terraform-aws-modules/ecr/aws ~> 3.0` |

Direct AWS resources are acceptable for small glue resources where a module
would hide the important behavior or add more surface area than it removes:
security groups, ALB listener rules, Route 53 records, WAF rules, VPC
endpoints, task-specific IAM policies, one-off support job definitions, and
small bucket policies or guardrails.

## Optional Extensions

Optional features stay visible in dedicated files instead of being mixed into
the base concerns:

- WAF: `optional_edge_waf.tf`.
- VPC endpoints: `optional_network_endpoints.tf`.
- ECS Exec support: `oidc_optional_features.tf` plus the SSM messages endpoint.
- Observability AWS deployment: not added yet; local Prometheus, Loki, and
  Grafana live under `docker/observability/`.
- Data hub compute: the S3 bucket exists; ECS data job and EventBridge schedule
  are not added yet. See `docs/data-flow.md`.

Some optional resources are currently enabled to preserve deployed behavior.
If a future change makes them toggleable, add a small, documented variable and
keep the default compatible with the current stack.

## When To Split

Do not split this directory into `infra/stacks/*` for neatness alone. A split is
justified only when at least one of these becomes true:

- Different resources must be applied by different teams or approval flows.
- A resource group has a materially different lifecycle or blast radius.
- Multiple AWS accounts or promotion environments are actually used.
- State locking or plan review becomes too noisy for a single PR.
- A reusable local module is needed by more than one real root.

Until then, prefer concern-based files in this root and keep PR plans easy to
review.

## Local Commands

```bash
terraform fmt -check -recursive infra/
cd infra && terraform validate
cd infra && tflint --init && tflint --format compact
checkov -d infra --framework terraform --config-file infra/.checkov.yaml
```

Use `make infra-plan` and `make infra-apply` for the normal operator path so
backend configuration stays consistent with CI.
