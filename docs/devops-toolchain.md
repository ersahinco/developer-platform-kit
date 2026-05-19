# DevOps Toolchain

This project standardizes a delivery toolchain for portable application
workloads. The current runtime is ECS Fargate; the reusable part is the review
shape around build, check, scan, deploy, and evidence.

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
| Dockerfiles | `make lint-dockerfiles` |
| Secrets | `make secret-scan` |
| Dependencies | `make dependency-audit` |
| Terraform | `terraform fmt`, `terraform validate`, TFLint, Checkov, reviewed plan, separate apply |

## Delivery Shape

- Pull requests validate before any cloud change.
- App build runs checks before image push.
- App deploy is manual and emits release evidence.
- Infra plan is reviewed before infra apply.
- Runtime-specific details may change later, but this gate shape should stay
  recognizable.

## Local Quality Commands

```bash
make lint
make secret-scan
make dependency-audit
uv run pytest tests/ -v
```

Prefer the dev container for the most reproducible workstation. Native host
setup is allowed; install only the tools you need and keep them aligned with CI.

## Conventions

- Keep workflows split by ownership: app build, app deploy, infra plan, infra
  apply, security, semgrep.
- Keep scripts small and explicit.
- Prefer metadata-driven behavior over repeated YAML logic.
- Keep workload intent in `platform/workloads.json`, but keep deploy sequence,
  cloud resource decisions, and operator choreography in workflows, scripts,
  and Terraform.
- Do not add a second CI system until there is a real operating need.
