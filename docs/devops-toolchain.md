# DevOps Toolchain

Quality-gate and workflow toolchain view. For rollout flow, use
[Deployment](deployment.md). For boundaries, use [Architecture](architecture.md).

## Current Toolchain

| Concern | Tool |
|---|---|
| Local orchestration | Docker Compose |
| Python workspace | `uv` |
| Tests | pytest |
| Python lint/format | Ruff |
| Python type checking | Pyright |
| Database migrations | Liquibase |
| Infrastructure as code | Terraform |
| Workflow linting | actionlint |
| Dockerfile linting | hadolint |
| Docs link checking | lychee |
| Policy as code | OPA / Conftest |
| Secret scanning | Gitleaks |
| Dependency audit | `pip-audit` |
| SAST | Semgrep CE |
| Image scanning | Trivy |
| CI/CD | GitHub Actions |
| Cloud auth | GitHub OIDC |

## Standard Gates

| Scope | Gate |
|---|---|
| App and scripts | Ruff, Pyright, pytest |
| Contract and repo shape | Focused pytest contract checks |
| Runtime conformance | `make runtime-conformance` |
| Workflows | `make lint-workflows` |
| Docs | `make lint-docs` |
| Policy | `make lint-policy` |
| Dockerfiles | `make lint-dockerfiles` |
| Secrets | `make secret-scan` |
| Dependencies | `make dependency-audit` |
| Terraform | `terraform fmt`, `terraform validate`, TFLint, Checkov, reviewed plan, separate apply |

Rule: pull requests validate before cloud change. Build before deploy. Plan
before apply. Cloud-changing workflows emit release evidence.

## GitHub Gate Matrix

| Workflow | Pull request role | Owned gates |
|---|---|---|
| `app-build.yml` | App and workload validation | Ruff format check, Ruff lint, Pyright, shell script syntax, pytest, runtime conformance |
| `security.yml` | Repo hygiene and dependency safety | `make secret-scan`, `make lint-docs`, `make lint-policy`, `make lint-workflows`, `make lint-dockerfiles`, `make dependency-audit` |
| `semgrep.yml` | Static application security testing | Semgrep CE scan for `apps/`, `packages/`, and `scripts/` |
| `infra-plan.yml` | Infrastructure validation and review evidence | `terraform fmt`, `terraform validate`, TFLint, Checkov, reviewed Terraform plan artifact/comment |

`app-deploy.yml` and `infra-apply.yml` are intentionally not pull-request
gates. They remain separate, reviewed, cloud-changing workflows.
