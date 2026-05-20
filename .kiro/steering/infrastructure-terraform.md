---
inclusion: fileMatch
fileMatchPattern: "infra/**/*.tf"
---

# Infrastructure (Terraform) Rules

Activated when working in `infra/`.

---

## Ownership Split — Never Cross These Boundaries

| Root | Owns |
|---|---|
| `infra/platform/` | Bootstrap, VPC/network, GitHub OIDC, shared platform concerns |
| `infra/app/` | Runtime resources: RDS, ECS cluster/services/tasks, ALB/WAF, jobs, messaging (SNS/SQS), observability wiring |
| `infra/catalog/` | Reusable AWS building blocks extracted for reuse — no direct deployment here |

Do not put app runtime resources in `infra/platform/`.
Do not put bootstrap or network resources in `infra/app/`.
Do not deploy directly from `infra/catalog/` — it is a library, not a root.

---

## Workload Inventory Rule

`infra/app/workload_inventory.tf` derives runtime values from `platform/workloads.json`.
It owns: runtime values, secret wiring, AWS-facing naming derived from the workload contract.
It must NOT redefine workload identity, operational class, or capability intent — those belong in `platform/workloads.json`.

Before adding a new resource for a workload, verify the workload exists in `platform/workloads.json`.

---

## Naming Conventions

- Resource names must derive from workload identity declared in `platform/workloads.json`
- Use consistent naming patterns: `{project}-{env}-{workload}-{resource-type}`
- Provider resource names (bucket names, queue ARNs, task definition families, IAM role names) stay in `infra/` — never leak into domain or application code

---

## Security Defaults

- IAM roles follow least-privilege — grant only what the workload explicitly needs
- No wildcard `*` actions or resources in IAM policies without a documented justification comment
- Secrets are injected at runtime via AWS Secrets Manager or SSM Parameter Store — never in tfvars, environment blocks, or committed files
- Security groups default to deny; open only required ports with explicit CIDR or security group references
- Run Checkov (`infra/.checkov.yaml` configures suppressions) before every plan

---

## Delivery Shape — Plan Before Apply

- `infra-plan.yml` runs on PR: `terraform fmt`, `terraform validate`, TFLint, Checkov, plan output posted for review
- `infra-apply.yml` runs manually after plan review — never auto-apply on push to main
- Every apply that changes cloud resources must emit release evidence
- Keep plan and apply as separate workflow triggers — this is intentional, do not merge them

---

## Terraform Style

- Use `terraform fmt` — all files must be formatted before commit
- Pin provider versions in `required_providers` — no open version ranges
- Use `terraform validate` and TFLint before every plan
- Prefer explicit resource references over data sources for resources owned in the same root
- Use `locals` to derive names from workload inventory rather than repeating string literals
- Add a comment when suppressing a Checkov rule — explain why the suppression is safe

---

## What Belongs at the Platform Edge (infra/) vs. the App Contract

| Belongs in infra/ | Belongs in platform/workloads.json |
|---|---|
| ECS task definition ARNs | Workload name and operational class |
| RDS endpoint and credentials wiring | Config and secret name declarations |
| ALB listener rules and target groups | Service port declarations |
| SNS topic ARNs and SQS queue URLs | Dapr pub/sub name and topic |
| CloudWatch alarm definitions | Observable behavior expectations |
| IAM role ARNs | (nothing — IAM is always platform edge) |

---

## Final Check Before Committing Terraform Changes

- [ ] `terraform fmt` applied
- [ ] `terraform validate` passes
- [ ] TFLint passes
- [ ] Checkov passes (or suppressions are documented)
- [ ] No secrets in tfvars, environment blocks, or committed files
- [ ] IAM policies follow least-privilege
- [ ] Plan reviewed before apply
- [ ] Workload exists in `platform/workloads.json` before its infra resources are created
