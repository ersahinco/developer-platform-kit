# Infrastructure

The repository distinguishes reusable infrastructure catalog material from
deployable stack assembly:

- `infra/catalog/` is the home for reusable AWS building blocks as real reuse
  appears.
- `infra/platform` and `infra/app` remain the current deployable Terraform
  roots. They are assembly roots, not the catalog.

The current extraction candidate map lives in
`infra/catalog/aws/extraction-map.md`. Use it before creating a new module so
the repo does not drift into speculative abstraction.

This doc is an infrastructure index, not the main architecture doc.

Use companion docs when the question is broader:

- [Architecture](../docs/architecture.md) for repo boundaries and placement
  rules
- [Deployment](../docs/deployment.md) for AWS rollout and operator flow
- [Runtime Toolkit](../docs/runtime-toolkit.md) for runtime-target evaluation

Terraform is still organized by lifecycle boundary:

- `platform/` owns AWS-bound bootstrap resources with an app-independent
  lifecycle: VPC networking, VPC endpoints, Route 53/account lookups, and the
  GitHub Actions OIDC role plus CI IAM policies.
- `app/` owns workload resources: RDS, ECS compute, ECR repositories, ALB/API
  edge, S3 data hub, scheduled jobs, Dapr-backed SNS/SQS queues, app IAM,
  CloudWatch app alarms, ALB access logs, and optional ADOT sidecar wiring.

`infra/` is an index and shared configuration boundary, not a runnable
Terraform root. Keep executable Terraform in the explicit lifecycle roots above
so platform bootstrap, workload runtime, and application delivery ownership do
not blur together.

## State Keys

| Root | State key |
|---|---|
| `infra/platform` | `<stack-name>/platform.tfstate` |
| `infra/app` | `<stack-name>/app.tfstate` |

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
