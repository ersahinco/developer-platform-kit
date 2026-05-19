# infra/ — Terraform Rules

Scoped rules for all Terraform under `infra/`.
The cross-tool base rules in root `AGENTS.md` apply here too.

---

## Root Ownership — Never Cross These Boundaries

| Root | Owns |
|---|---|
| `infra/platform/` | Bootstrap, VPC/network, GitHub OIDC, shared platform concerns |
| `infra/app/` | RDS, ECS cluster/services/tasks, ALB/WAF, jobs, SNS/SQS, observability wiring |
| `infra/catalog/` | Reusable AWS building blocks — library only, not a deploy root |

Do not put app runtime resources in `infra/platform/`.
Do not put bootstrap or network resources in `infra/app/`.
Do not deploy directly from `infra/catalog/`.

---

## Workload Inventory Rule

`infra/app/workload_inventory.tf` derives runtime values from `platform/workloads.json`.
It owns runtime values, secret wiring, and AWS-facing naming.
It must NOT redefine workload identity or operational class — those belong in `platform/workloads.json`.

Verify the workload exists in `platform/workloads.json` before creating its infra resources.

---

## Security Defaults

- IAM roles follow least-privilege — no wildcard `*` actions without a documented justification comment
- Secrets injected at runtime via Secrets Manager or SSM — never in tfvars, environment blocks, or committed files
- Security groups default to deny; open only required ports with explicit references
- Run Checkov (`infra/.checkov.yaml` configures suppressions) before every plan

---

## Delivery Shape

- `infra-plan.yml`: fmt → validate → TFLint → Checkov → plan (post for review)
- `infra-apply.yml`: manual trigger only, after plan review — never auto-apply on push
- Every apply emits release evidence

---

## Terraform Style

- `terraform fmt` before every commit
- Pin provider versions in `required_providers` — no open ranges
- Use `locals` to derive names from workload inventory rather than repeating string literals
- Add a comment when suppressing a Checkov rule — explain why it is safe
- Prefer explicit resource references over data sources for resources owned in the same root

---

## What Belongs in infra/ vs platform/workloads.json

| infra/ | platform/workloads.json |
|---|---|
| ECS task definition ARNs | Workload name and operational class |
| RDS endpoint and credentials wiring | Config and secret name declarations |
| ALB listener rules and target groups | Service port declarations |
| SNS topic ARNs and SQS queue URLs | Dapr pub/sub name and topic |
| CloudWatch alarm definitions | Observable behavior expectations |
| IAM role ARNs | (always platform edge) |
