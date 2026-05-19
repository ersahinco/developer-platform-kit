# App Terraform Root

This root owns workload resources:

- App database persistence and database security groups.
- ECS cluster, app service, support tasks, and ECR repositories.
- ALB/API edge, ACM certificate, and app DNS record.
- Object storage, EventBridge schedules, messaging, and app IAM.
- CloudWatch app-level alarms while they remain the AWS-native rollback signal.
- Local-first observability wiring: CloudWatch logs, ALB access logs, and an
  optional ADOT sidecar.

It consumes platform outputs through S3 remote state. Do not define VPC,
subnets, Route 53 zone lookups, or the GitHub OIDC role identity here.

The Grafana, Loki, Prometheus, and Tempo assets under
`platform/concerns/observability/` are the portable local analysis surface. Do
not add ECS services for them unless the project intentionally reintroduces
hosted observability as a separate module.

Terraform files are named by app capability or durable infrastructure layer.
AWS-specific implementation details stay inside the capability file unless they
are shared across multiple capabilities. For example, `messaging.tf` owns SQS
queues, publisher IAM, and DLQ alarms together; `object_storage.tf` owns S3
bucket guardrails; ECS Exec permissions live with app compute because they
support the app ECS service.

Before extracting a capability into `infra/catalog/aws`, check
`../catalog/aws/extraction-map.md`. If the capability does not have a second
real consumer or a stable repeated pattern yet, keep it here.
