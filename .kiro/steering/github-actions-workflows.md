---
inclusion: fileMatch
fileMatchPattern: ".github/workflows/*.yml"
---

# GitHub Actions Workflow Rules

Activated when working in `.github/workflows/`.

## Workflow Ownership

| Workflow | Owns |
|---|---|
| `app-build.yml` | Validate, test, runtime conformance, build image, scan, push to registry |
| `app-deploy.yml` | Migrate DB, deploy workloads, verify health, register support workloads, emit release evidence |
| `infra-plan.yml` | Terraform fmt, validate, TFLint, Checkov, plan, review output |
| `infra-apply.yml` | Terraform apply after reviewed plan |
| `security.yml` | Gitleaks secret scan, pip-audit dependency audit, Trivy image scan |
| `semgrep.yml` | Semgrep SAST scan |
| `app-rollback-drill.yml` | App image rollback drill |
| `data-runtime-rollback-drill.yml` | Data-phase rollback drill |

Keep build separate from deploy. Keep plan separate from apply. Keep security
and SAST separate.

## Hard Rules

- Use GitHub OIDC for AWS authentication. No long-lived access keys in secrets.
- Reference OIDC role ARNs through `vars.*` or `secrets.*`. Do not hardcode account IDs, role ARNs, or region strings.
- Always tag images with `${{ github.sha }}`. Never use `latest`.
- Every cloud-changing workflow emits a release event via `scripts/observability/release_event.py`.
- `app-deploy.yml` runs only after a successful `app-build.yml` for the same SHA.
- `infra-apply.yml` runs only after a reviewed `infra-plan.yml` for the current default-branch SHA.
- Add explicit `permissions:` blocks with least privilege.

## Style

- Prefer metadata-driven workflow logic. Use `platform/workloads.json` as the workload source of truth.
- Keep steps small and clearly named.
- Pin security-sensitive actions by full SHA.
- Use `$GITHUB_OUTPUT` and `$GITHUB_ENV`, not deprecated `set-output`.
- Do not swallow gate failures with `continue-on-error`.
- Do not store secrets in workflow files.
- Run `make lint-workflows` before committing workflow changes.

## Rollback Categories

| Category | Mechanism |
|---|---|
| App image rollback | Re-deploy previous immutable image tag |
| Runtime data-phase rollback | Forward-fix or documented restore procedure |
| Infra rollback | Reviewed plan/apply with previous state |
| Job recovery | Idempotent rerun, forward fix, or documented data restore |

When adding a workflow, extend an existing ownership boundary first. If a new
workflow is still needed, document its owner here.
