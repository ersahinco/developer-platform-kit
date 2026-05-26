# Infrastructure

`infra/` is the Terraform boundary, not a deploy root.

| Path | Owns |
|---|---|
| `infra/platform/` | Bootstrap, network, GitHub OIDC for the current AWS runtime |
| `infra/app/` | Current AWS runtime resources |
| `infra/catalog/` | Reusable runtime-target catalog building blocks |

Use `infra/catalog/<runtime-target>/` for catalog growth. The current catalog
surface is `infra/catalog/aws/`. `infra/catalog/managed-kubernetes/` is
reserved for future managed-Kubernetes reusable modules when a real workload
needs them. `infra/catalog/managed-service-provider/` is reserved for reusable
provider-edge building blocks such as managed Postgres or DNS integrations when
cost or hybrid design requires them.

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
