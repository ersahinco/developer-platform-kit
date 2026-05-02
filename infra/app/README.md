# App Terraform Root

This root owns workload resources:

- App database persistence and database security groups.
- ECS cluster, app service, support tasks, and ECR repositories.
- ALB/API edge, ACM certificate, and app DNS record.
- Object storage, EventBridge schedules, messaging, and app IAM.
- CloudWatch app-level alarms while they remain in dual-run.
- Optional Grafana/Loki/Prometheus observability.

It consumes platform outputs through S3 remote state. Do not define VPC,
subnets, Route 53 zone lookups, or the GitHub OIDC role identity here.

The optional Grafana stack should reuse portable app observability assets from
the repository-level `observability/` folder. Keep AWS-only rendering templates
under `infra/app/templates/observability/` when ECS storage or service discovery
must differ from local Compose.

Terraform files are named by app capability or durable infrastructure layer.
AWS-specific implementation details stay inside the capability file unless they
are shared across multiple capabilities. For example, `messaging.tf` owns SQS
queues, publisher IAM, and DLQ alarms together; `object_storage.tf` owns S3
bucket guardrails; ECS Exec permissions live with app compute because they
support the app ECS service.
