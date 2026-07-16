# infra/ Rules

Root `AGENTS.md` applies here too.

## Root Ownership

| Root | Owns |
|---|---|
| `infra/platform/` | Bootstrap, VPC/network, GitHub OIDC, shared platform concerns for the current AWS runtime |
| `infra/app/` | RDS, ECS, ALB/WAF, jobs, messaging, observability wiring for the current AWS runtime |
| `infra/catalog/` | Reusable runtime-target building blocks; current AWS catalog lives under `infra/catalog/aws/` |
| `infra/hybrid-reference/` | Explicit data, compute, and DNS roots for the starter hybrid reference |

Do not put app runtime resources in `infra/platform/`.
Do not put bootstrap or network resources in `infra/app/`.
Do not deploy from `infra/catalog/`.

## Rules

- `infra/app/workload_inventory.tf` fulfills `platform/workloads.json`; it must not redefine workload identity or class.
- Add future runtime targets as additive siblings; keep provider realizations explicit and discoverable through stable catalog IDs.
- Verify the workload exists in `platform/workloads.json` before adding its infra resources.
- IAM is least-privilege only.
- Secrets live in Secrets Manager or SSM, never tfvars or committed files.
- Run Checkov before every plan.
- Keep `infra-plan.yml` and `infra-apply.yml` separate.
- Run `terraform fmt`; pin providers; prefer `locals` for derived names; document Checkov suppressions.
