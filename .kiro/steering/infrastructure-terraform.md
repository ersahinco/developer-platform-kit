---
inclusion: fileMatch
fileMatchPattern: "infra/**/*.tf"
---

# Infrastructure (Terraform) Rules

Activated when working in `infra/`.

## Ownership

| Root | Owns |
|---|---|
| `infra/platform/` | Bootstrap, VPC/network, GitHub OIDC, shared platform concerns |
| `infra/app/` | RDS, ECS, ALB/WAF, jobs, messaging, observability wiring |
| `infra/catalog/` | Reusable AWS building blocks only |

## Rules

- Do not cross the root ownership boundaries above.
- `infra/app/workload_inventory.tf` fulfills `platform/workloads.json`; it must not redefine workload identity or class.
- Derive resource names from the workload contract.
- IAM is least-privilege only.
- Secrets live in Secrets Manager or SSM, never tfvars or committed files.
- Run `terraform fmt`, `terraform validate`, TFLint, and Checkov before plan review.
- Keep `infra-plan.yml` and `infra-apply.yml` separate.
