# DevOps Toolchain

Quality-gate and workflow toolchain map.

Use [Deployment](deployment.md) for rollout flow and
[Architecture](architecture.md) for repo boundaries.

## Toolchain

| Concern | Tool |
|---|---|
| local orchestration | Docker Compose |
| Python workspace | `uv` |
| tests | pytest |
| lint and format | Ruff |
| type checking | Pyright |
| database migrations | Liquibase |
| infrastructure as code | Terraform |
| workflow linting | actionlint |
| Dockerfile linting | hadolint |
| docs link checking | lychee |
| policy as code | OPA / Conftest |
| secret scanning | Gitleaks |
| dependency audit | `pip-audit` |
| SAST | Semgrep CE |
| image scanning | Trivy |
| CI/CD | GitHub Actions |
| cloud auth | GitHub OIDC |

## Standard Gates

| Scope | Gate |
|---|---|
| app and scripts | Ruff, Pyright, pytest |
| contract and repo shape | focused pytest contract checks |
| runtime conformance | `make runtime-conformance` |
| workflows | `make lint-workflows` |
| docs | `make lint-docs` |
| policy | `make lint-policy` |
| Dockerfiles | `make lint-dockerfiles` |
| secrets | `make secret-scan` |
| dependencies | `make dependency-audit` |
| Terraform | `terraform fmt`, `terraform validate`, TFLint, Checkov, reviewed plan, separate apply |

Rules:

- pull requests validate before cloud change
- build before deploy
- plan before apply
- cloud-changing workflows emit release evidence

## GitHub Gate Matrix

| Workflow | Pull request role | Owned gates |
|---|---|---|
| `app-build.yml` | app and workload validation | Ruff format check, Ruff lint, Pyright, shell script syntax, pytest, runtime conformance |
| `security.yml` | repo hygiene and dependency safety | `make secret-scan`, `make lint-docs`, `make lint-policy`, `make lint-workflows`, `make lint-dockerfiles`, `make dependency-audit` |
| `semgrep.yml` | static application security testing | Semgrep CE scan for `apps/`, `packages/`, and `scripts/` |
| `infra-plan.yml` | infrastructure validation and review evidence | `terraform fmt`, `terraform validate`, TFLint, Checkov, reviewed Terraform plan artifact/comment |

`app-deploy.yml`, `data-support-deploy.yml`, `data-schema-apply.yml`,
`data-runtime-switch.yml`, `data-backfill.yml`, rollback drills, and
`infra-apply.yml` remain separate reviewed cloud-changing workflows, not
pull-request gates.
