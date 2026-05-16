# DevOps Toolchain

This project standardizes the delivery toolchain for portable application
workloads. The current runtime is ECS Fargate, but the reusable part is the
build, check, scan, evidence, and review shape.

## Current Toolchain

| Concern | Current mechanism |
|---|---|
| Source control | Git monorepo |
| Local orchestration | Docker Compose |
| Standard workstation | Dev Container with pinned project quality tools installed |
| Native workstation | Best-effort manual setup from mainstream project or vendor channels |
| Python dependency management | `uv` workspace |
| Python dependency updates | Dependabot weekly `uv` updates |
| Local commit checks | pre-commit hooks |
| Tests | pytest |
| Python lint/format | ruff |
| Python type checking | pyright, aligned with Pylance diagnostics |
| Shell script syntax | `find scripts -name '*.sh' -print0 \| xargs -0 bash -n` |
| Documentation links | lychee |
| GitHub workflow linting | actionlint |
| Dockerfile linting | hadolint |
| Database migrations | Liquibase |
| Infrastructure as code | Terraform |
| Infrastructure checks | terraform fmt, terraform validate, tflint, checkov |
| CI/CD | GitHub Actions |
| GitHub Actions updates | Dependabot weekly action updates |
| AWS authentication | GitHub OIDC role assumption |
| Secret scanning | Gitleaks |
| Python dependency audit | Direct `pip-audit` against a frozen `uv.lock` export |
| SAST | Semgrep Community Edition |
| Image registry | ECR |
| Image security | Trivy before push, ECR scanning configured in Terraform |
| Runtime | ECS Fargate |

## Standard Gates

GitHub Actions is the current delivery control plane. The portable contract is
the gate shape: the same app, contract, security, workflow, docs, image, and
Terraform checks should run before code reaches deployable artifacts.

| Scope | Gate |
| --- | --- |
| App and scripts | Ruff format check, Ruff lint, Pyright, pytest. |
| Platform contracts | `uv run python scripts/ci/validate_platform_contract.py`. |
| Runtime conformance | `make runtime-conformance` builds and runs declared workload containers. |
| Workflows | actionlint through `make lint-workflows`. |
| Docs | lychee through `make lint-docs`. |
| Dockerfiles | hadolint through `make lint-dockerfiles`. |
| Secrets | Gitleaks through `make secret-scan`. |
| Dependencies | `pip-audit` against the frozen `uv.lock` export. |
| SAST | Semgrep Community Edition in CI. |
| Images | Trivy before push and registry scan-on-push. |
| Terraform | `terraform fmt`, `terraform validate`, TFLint, Checkov, reviewed plan, separate apply. |

## Delivery Shape

- Pull requests run validation before any cloud change.
- App build runs tests, contract validation, runtime conformance, image build,
  and image scan before push.
- App deploy is manual and emits release evidence.
- Infra plan is reviewed before infra apply.
- Runtime-specific workflow steps may differ later, but the gate shape should
  stay recognizable.

Do not add a second CI system or duplicate pipeline files until the repo needs
to run there. Document equivalence first, then implement only when it becomes
an operating requirement.

## Workstation Baseline

Prefer the dev container for exact reproducibility. It pins the daily toolchain
used by the project: Python 3.14, `uv`, Terraform 1.15.0, Go 1.26.2,
Node.js 24 LTS, npm 11.13.0, TypeScript 6.0.3, AWS CLI v2, TFLint, Checkov,
pre-commit, actionlint, lychee, hadolint, gitleaks, and Docker CLI/Compose
access.

Native host setup is optional. Install only the tools you need from mainstream
project or vendor channels and keep them aligned with this document,
`pyproject.toml`, the dev container, and CI images. Terraform should come from
HashiCorp's signed release channel for the exact stable version. Stay on stable
releases and avoid preview or release-candidate builds for project tooling.

## Hardening Goals

- Keep `.pre-commit-config.yaml` aligned with `make lint` and `make fmt`.
- Keep all quality gates runnable locally and in CI.
- Keep AWS-changing workflows split so humans review Terraform plan output or
  build/scan results before triggering apply or deploy.
- Keep scripts small, explicit, and easy to inspect.

## Local Quality Commands

For the most reproducible workstation, open the repository in the dev
container. It is intentionally a development shell, not another app runtime:
the existing Docker Compose services still provide Postgres, PgBouncer,
Liquibase, the API, workers, and data jobs.

```bash
make pre-commit
make secret-scan
make dependency-audit
make lint-scripts
make lint-docs
make lint-workflows
make lint-dockerfiles
make lint
make fmt
uv run pytest tests/ -v
```

`ruff`, `pyright`, and `pip-audit` are declared in the root development
dependency group. Standard ecosystem tools own generic checks: Gitleaks scans
for committed secrets, lychee checks documentation links, actionlint validates
workflow syntax and expressions, and hadolint checks Dockerfile hygiene. The
dependency audit exports the resolved `uv.lock` graph to a temporary
requirements file and runs `pip-audit` against those exact pins.

Pre-commit runs lightweight file hygiene, Ruff, Terraform fmt, shell script
syntax checks, standard docs/workflow/Dockerfile checks, Gitleaks, and Pyright.
Pyright is intentionally included because type regressions are cheap to catch
before commit and have already been a repo-wide quality goal. Network-backed or
slower checks stay in Make and CI: dependency audit, TFLint, Checkov, Semgrep,
Terraform validate/plan, Docker builds, Trivy, and pytest.

Semgrep Community Edition runs in GitHub Actions as the repo's SAST gate. It is
kept out of pre-commit because full-code SAST is slower than the local edit loop
and should run consistently in CI.

SBOM generation remains deferred until a CI upload, registry attachment,
release artifact, or compliance process consumes it. Generating an unused SBOM
would add churn without improving operator behavior.

Security exceptions remain inline in the relevant tool configuration until
there is a real cross-tool exception process. Do not add
`security/exceptions.yaml` as an empty placeholder.

Dependabot uses the `uv` ecosystem for Python dependency updates and the
`github-actions` ecosystem for workflow action updates.

The App Build workflow runs Trivy before pushing first-party app, worker, data
export, Liquibase, and the patched PgBouncer sidecar image to ECR. Terraform
also enables ECR scan-on-push for each managed repository.

Base image digest pinning remains deferred until automated digest renewal is
added in the same change. Mutable version tags are less strict, but they avoid
quietly freezing stale base layers without a renewal workflow.

## Naming Conventions

Keep names boring and ownership-oriented:

| Area | Convention |
|---|---|
| Apps | `apps/<runtime_entrypoint>/`, for example `api`, `backfill_worker`, `data_export_job`. |
| Packages | `packages/<library>/` with import names matching the folder, for example `domain`, `application`, `infrastructure`. |
| Terraform files | Name files by app-owned domain, platform concern, or durable capability layer, such as `edge.tf`, `database.tf`, `compute_ecs.tf`, `messaging.tf`, `object_storage.tf`, `workload_jobs.tf`, `observability.tf`, `network.tf`, and `github_actions.tf`. Keep necessary auxiliary resources next to the capability they support, including IAM policies and monitoring alarms. |
| CI scripts | `scripts/ci/` for GitHub Actions/AWS deployment helpers. |
| Local/operator scripts | Verb-first or domain-first helpers under `scripts/operator/`, `scripts/release/`, `scripts/observability/`, and `scripts/data/`. |
| Local tool entrypoints | Keep conventional root files at root: `compose.yaml`, `pyproject.toml`, `uv.lock`, `Makefile`, and `.dockerignore`. |
| Local support assets | Put owned support config under the domain folder, for example `observability/`, `db/`, or `.devcontainer/`. |

Do not add empty top-level folders from an inspired architecture. Create a new
folder only when there is real content, a clear owner, and a local or CI check
that keeps it alive.
