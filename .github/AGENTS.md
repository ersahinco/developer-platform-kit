# .github/workflows/ — GitHub Actions Rules

Scoped rules for all workflows under `.github/workflows/`.
The cross-tool base rules in root `AGENTS.md` apply here too.

---

## Workflow Ownership — One Concern Per Workflow

| Workflow | Owns |
|---|---|
| `app-build.yml` | Validate, test, runtime conformance, build image, scan, push, emit build evidence |
| `app-deploy.yml` | Migrate DB, deploy, verify health, register support workloads, emit release evidence |
| `infra-plan.yml` | terraform fmt, validate, TFLint, Checkov, plan — post for review |
| `infra-apply.yml` | terraform apply — manual trigger only, after plan review, emit release evidence |
| `security.yml` | Gitleaks, pip-audit, docs/workflow/Dockerfile lint |
| `semgrep.yml` | Semgrep SAST |
| `app-rollback-drill.yml` | App image rollback drill |
| `data-runtime-rollback-drill.yml` | Data-phase rollback drill |

Do not merge build and deploy. Do not merge plan and apply.

---

## Non-Negotiable Rules

- **OIDC only** — no long-lived AWS access keys stored as secrets
- **Immutable tags** — always `${{ github.sha }}`, never `latest`
- **Release evidence** — every cloud-changing workflow emits a release event via `scripts/observability/release_event.py`
- **Separate triggers** — `app-deploy` runs after a successful `app-build` for the same SHA; `infra-apply` runs after a reviewed `infra-plan`
- **`permissions:` blocks** — explicit and least-privilege on every workflow
- **Pinned action versions** — use full SHA for security-sensitive steps

---

## Style

- Prefer metadata-driven behavior — use `platform/workloads.json` as the source of truth for workload lists
- Step names describe what the step does, not how
- Use `$GITHUB_OUTPUT` and `$GITHUB_ENV` — not deprecated `set-output`
- `continue-on-error: false` (default) for all gates — do not silently swallow failures
- Run `make lint-workflows` (actionlint) before committing any workflow change

---

## Rollback Categories — Keep Separate

| Category | Mechanism |
|---|---|
| App image rollback | Re-deploy previous immutable image tag |
| Runtime data-phase rollback | Forward-fix or documented restore procedure |
| Infra rollback | Reviewed plan/apply with previous state |
| Job recovery | Idempotent rerun, forward fix, or documented data restore |
