# .github/workflows/ Rules

Root `AGENTS.md` applies here too.

## Ownership

| Workflow | Owns |
|---|---|
| `app-build.yml` | Validate, test, runtime conformance, build, scan, push, build evidence |
| `app-deploy.yml` | Deploy service revisions, verify, release evidence |
| `data-support-deploy.yml` | Promote support job image revisions, release evidence |
| `data-runtime-switch.yml` | Reviewed runtime mode transitions, release evidence |
| `data-schema-apply.yml` | Reviewed schema apply, release evidence |
| `data-backfill.yml` | Reviewed backfill execution, release evidence |
| `operational-snapshot.yml` | Reviewed operational snapshot execution, release evidence |
| `infra-plan.yml` | `terraform fmt`, validate, TFLint, Checkov, reviewed plan |
| `infra-apply.yml` | Apply reviewed plan, release evidence |
| `security.yml` | Secret, dependency, docs, workflow, Dockerfile checks |
| `semgrep.yml` | SAST |

Keep build separate from deploy. Keep plan separate from apply.

## Hard Rules

- OIDC only. No long-lived AWS access keys.
- Immutable tags only: `${{ github.sha }}`, never `latest`.
- Every cloud-changing workflow emits `scripts/observability/release_event.py`.
- `app-deploy.yml` follows successful `app-build.yml` for the same SHA.
- `data-*.yml` workflows follow successful `app-build.yml` for the same SHA when they promote or execute workload images.
- `infra-apply.yml` follows reviewed `infra-plan.yml`.
- Use explicit least-privilege `permissions:`.
- Pin security-sensitive actions by full SHA.

## Style

- Use `platform/workloads.json` as the workload source of truth.
- Use `$GITHUB_OUTPUT` and `$GITHUB_ENV`, not `set-output`.
- Do not swallow gate failures with `continue-on-error`.
- Run `make lint-workflows` before commit.
