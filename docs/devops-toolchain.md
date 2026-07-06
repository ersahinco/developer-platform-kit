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
| typo linting | typos |
| Markdown style linting | markdownlint |
| type checking | Pyright |
| database migrations | Liquibase |
| infrastructure as code | Terraform |
| Terraform version updates | `tfupdate` |
| workflow linting | actionlint |
| Dockerfile linting | hadolint |
| docs link checking | lychee |
| Git hook runner | `prek` |
| commit message linting | Conventional Commit lint |
| policy as code | OPA / Conftest |
| IaC scanning | Checkov |
| policy scanning | OPA / Conftest |
| secret scanning | Gitleaks, Deepfence SecretScanner for images |
| dependency audit | `pip-audit`, OWASP Dependency-Check |
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
| text hygiene | `make lint-text` |
| policy | `make lint-policy` |
| Dockerfiles | `make lint-dockerfiles` |
| secrets | `make secret-scan` |
| dependencies | `make dependency-audit` |
| containers | `make container-scan` |
| IaC | `make iac-scan` |
| policy | `make policy-scan` |
| extended security | `make security-readiness-deep` |
| cloud security readiness | `make security-readiness` |
| Terraform | `terraform fmt`, `terraform validate`, TFLint, Checkov, reviewed plan, separate apply |

Rules:

- pull requests validate before cloud change
- build before deploy
- plan before apply
- cloud-changing workflows emit release evidence
- use OSS/local-first scanners for required gates; paid SaaS tools such as
  hosted Sonar or Palo Alto/Prisma surfaces may complement this toolkit but
  are not required delivery dependencies

## GitHub Gate Matrix

| Workflow | Pull request role | Owned gates |
|---|---|---|
| `app-build.yml` | app and workload validation | Ruff format check, Ruff lint, Pyright, shell script syntax, pytest, runtime conformance |
| `local-kubernetes-contracts.yml` | static local Kubernetes validation | manifest-to-workload contract, runtime defaults, local-kubernetes capability proof |
| `security.yml` | repo hygiene and dependency safety | `make secret-scan`, `make lint-docs`, `make lint-policy`, `make lint-workflows`, `make lint-dockerfiles`, `make dependency-audit` |
| `semgrep.yml` | static application security testing | Semgrep CE scan for `apps/`, `packages/`, and `scripts/` |
| `infra-plan.yml` | infrastructure validation and review evidence | `terraform fmt`, `terraform validate`, TFLint, Checkov, reviewed Terraform plan artifact/comment |

`app-deploy.yml`, `data-support-deploy.yml`, `data-schema-apply.yml`,
`data-runtime-switch.yml`, `data-backfill.yml`, and `infra-apply.yml` remain
separate reviewed cloud-changing workflows, not pull-request gates.

Pipeline template rule: keep these workflows copyable before extracting shared
workflow packages. Prefer ordinary GitHub Actions, explicit `workflow_call`
inputs only after repeated reuse, immutable image tags, pinned third-party
actions, and portable evidence artifacts over custom orchestrators.
