# Infrastructure

Terraform is organized by lifecycle boundary:

- `platform/` owns AWS-bound bootstrap resources with an app-independent
  lifecycle: VPC networking, VPC endpoints, Route 53/account lookups, and the
  GitHub Actions OIDC role plus CI IAM policies.
- `app/` owns workload resources: RDS, ECS compute, ECR repositories, ALB/API
  edge, S3 data hub, scheduled jobs, Dapr-backed SNS/SQS queues, app IAM, CloudWatch app
  alarms, and optional Grafana/Loki/Prometheus observability.

`infra/` is an index and shared configuration boundary, not a runnable
Terraform root. Keep executable Terraform in the explicit lifecycle roots above
so platform bootstrap, workload runtime, and application delivery ownership do
not blur together.

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
