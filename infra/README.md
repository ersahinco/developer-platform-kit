# Infrastructure

`infra/` is the Terraform boundary, not a deploy root.

| Path | Owns |
|---|---|
| `infra/platform/` | Bootstrap, network, GitHub OIDC |
| `infra/app/` | Runtime resources |
| `infra/catalog/` | Reusable AWS building blocks |

Use `infra/catalog/aws/extraction-map.md` before creating a module.

Companion docs:

- [Architecture](../docs/architecture.md)
- [Deployment](../docs/deployment.md)
- [Runtime Toolkit](../docs/runtime-toolkit.md)

## State Keys

| Root | State key |
|---|---|
| `infra/platform` | `<stack-name>/platform.tfstate` |
| `infra/app` | `<stack-name>/app.tfstate` |

## Commands

```bash
make infra-platform-plan
make infra-platform-apply
make infra-app-plan
make infra-app-apply
```

## Validation

```bash
terraform fmt -check -recursive infra/
terraform -chdir=infra/platform validate
terraform -chdir=infra/app validate
checkov -d infra --framework terraform --config-file infra/.checkov.yaml
```
