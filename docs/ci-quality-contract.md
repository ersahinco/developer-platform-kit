# CI Quality Contract

GitHub Actions is the current delivery control plane. The portable contract is
the gate shape: the same app, contract, security, workflow, docs, image, and
Terraform checks should run before code reaches deployable artifacts.

## Standard Gates

| Scope | Gate |
| --- | --- |
| App and scripts | Ruff format check, Ruff lint, Pyright, pytest. |
| Platform contracts | `uv run python scripts/ci/validate_platform_contract.py`. |
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
- App build runs tests, contract validation, image build, and image scan before
  push.
- App deploy is manual and emits release evidence.
- Infra plan is reviewed before infra apply.
- Runtime-specific workflow steps may differ later, but the gate shape should
  stay recognizable.

Do not add a second CI system or duplicate pipeline files until the repo needs
to run there. Document equivalence first, then implement only when it becomes an
operating requirement.
