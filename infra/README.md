# Infrastructure

Terraform is organized by lifecycle boundary:

- `platform/` owns AWS-bound bootstrap resources with an app-independent
  lifecycle: VPC networking, VPC endpoints, Route 53/account lookups, and the
  GitHub Actions OIDC role plus CI IAM policies.
- `app/` owns workload resources: RDS, ECS compute, ECR repositories, ALB/API
  edge, S3 data hub, scheduled jobs, Dapr-backed SNS/SQS queues, app IAM, CloudWatch app
  alarms, and optional Grafana/Loki/Prometheus observability.

There is no Terraform root directly in `infra/` anymore. The old single-root
state key, `aws-sdlc-containers/stack.tfstate`, has been retired. Use the split
roots only. The empty retired object was archived under
`aws-sdlc-containers/retired/stack.tfstate-2026-05-01.json` and removed from
the active state prefix on May 2, 2026.

## State Keys

| Root | State key |
|---|---|
| `infra/platform` | `aws-sdlc-containers/platform.tfstate` |
| `infra/app` | `aws-sdlc-containers/app.tfstate` |

## Operator Commands

```bash
make infra-platform-plan
make infra-platform-apply
make infra-app-plan
make infra-app-apply
```

`make infra-plan` runs platform then app plans. `make infra-apply` applies
platform then app. Read outputs from the owning root, for example
`terraform -chdir=infra/app output api_fqdn`.

## Validation

```bash
terraform fmt -check -recursive infra/
terraform -chdir=infra/platform validate
terraform -chdir=infra/app validate
checkov -d infra --framework terraform --config-file infra/.checkov.yaml
```
