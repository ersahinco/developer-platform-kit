---
inclusion: fileMatch
fileMatchPattern: ".github/workflows/*.yml"
---

# GitHub Actions Workflow Rules

Activated when working in `.github/workflows/`.

---

## Workflow Ownership — One Concern Per Workflow

| Workflow | Owns |
|---|---|
| `app-build.yml` | Validate, test, runtime conformance, build image, scan, push to registry |
| `app-deploy.yml` | Migrate DB, deploy workloads, verify health, register support workloads, emit release evidence |
| `infra-plan.yml` | Terraform fmt, validate, TFLint, Checkov, plan — post output for review |
| `infra-apply.yml` | Terraform apply — manual trigger only, after plan review |
| `security.yml` | Gitleaks secret scan, pip-audit dependency audit, Trivy image scan |
| `semgrep.yml` | Semgrep SAST scan |
| `app-rollback-drill.yml` | App image rollback drill |
| `data-runtime-rollback-drill.yml` | Data-phase rollback drill |

Do not merge build and deploy into one workflow.
Do not merge infra-plan and infra-apply into one workflow.
Keep security and SAST as separate workflows — they run on their own schedule and triggers.

---

## Cloud Auth — OIDC Only

- Use GitHub OIDC for AWS authentication — no long-lived access keys stored as secrets
- OIDC role ARNs are provisioned by `infra/platform/` and referenced as workflow secrets/vars
- Never hardcode AWS account IDs, role ARNs, or region strings in workflow files — use `vars.*` or `secrets.*`

---

## Image Tagging — Immutable Tags

- Always tag images with the Git SHA: `${{ github.sha }}`
- Never use `latest` as the deployed tag — it is not immutable and breaks rollback
- The deploy workflow must reference the exact image tag built by the build workflow

---

## Release Evidence — Required for Cloud-Changing Workflows

Every workflow that changes cloud state must emit a release event. The release event must include:
- What changed (workload name, image tag, migration status)
- Which revision ran (Git SHA, workflow run ID)
- Which workflow applied it
- What verification happened (health check results, alarm state)

Use `scripts/observability/release_event.py` for the portable release event format.

---

## Delivery Gates — Order Matters

```
app-build  →  (manual approval)  →  app-deploy
infra-plan  →  (manual review)  →  infra-apply
```

- `app-deploy` must only run after a successful `app-build` for the same SHA
- `infra-apply` must only run after a reviewed `infra-plan` output
- Never auto-apply infrastructure changes on push to main

---

## Workflow Style Rules

- Prefer metadata-driven behavior over repeated YAML logic — use `platform/workloads.json` as the source of truth for workload lists
- Keep steps small and named clearly — each step name should describe what it does, not how
- Pin action versions with full SHA (`uses: actions/checkout@<sha>`) for security-sensitive steps
- Use `continue-on-error: false` (the default) for all gates — do not silently swallow failures
- Avoid `set-output` (deprecated) — use `$GITHUB_OUTPUT` and `$GITHUB_ENV`
- Do not store secrets in workflow files — use `secrets.*` context only
- Add `permissions:` blocks explicitly — follow least-privilege for GITHUB_TOKEN

---

## Rollback Categories — Keep Separate

| Category | Mechanism |
|---|---|
| App image rollback | Re-deploy previous immutable image tag |
| Runtime data-phase rollback | Documented forward-fix or restore procedure |
| Infra rollback | Reviewed plan/apply with previous state |
| Job recovery | Idempotent rerun, forward fix, or documented data restore |

Do not conflate these. Each has its own workflow or runbook.

---

## Adding a New Workflow

Before adding a new workflow:
1. Check whether an existing workflow can be extended with a new job
2. If a new workflow is needed, document its ownership boundary in this file
3. Run `make lint-workflows` (actionlint) before committing

---

## Final Check Before Committing Workflow Changes

- [ ] Build and deploy are separate workflows
- [ ] Plan and apply are separate workflows
- [ ] OIDC auth — no long-lived keys
- [ ] Immutable image tags (Git SHA)
- [ ] Release evidence emitted for cloud-changing steps
- [ ] Action versions pinned
- [ ] `permissions:` blocks explicit and least-privilege
- [ ] `make lint-workflows` passes
