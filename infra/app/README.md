# App Terraform Root

This root owns workload resources:

- RDS and database security groups.
- ECS cluster, app service, support tasks, and ECR repositories.
- ALB/API edge, ACM certificate, and app DNS record.
- S3 data hub, EventBridge schedule, SQS queues, and app IAM.
- CloudWatch app-level alarms while they remain in dual-run.
- Optional Grafana/Loki/Prometheus observability.

It consumes platform outputs through S3 remote state. Do not define VPC,
subnets, Route 53 zone lookups, or the GitHub OIDC role identity here.

The optional Grafana stack should reuse portable app observability assets from
the repository-level `observability/` folder. Keep AWS-only rendering templates
under `infra/app/templates/observability/` when ECS storage or service discovery
must differ from local Compose.
