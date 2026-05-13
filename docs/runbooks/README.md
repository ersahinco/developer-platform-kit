# Runbooks

Use these during AWS incidents, failed deploys, and alarm investigations.

| Situation | Runbook |
|---|---|
| Public API errors or latency | [App Edge Errors Or Latency](app-edge-errors-latency.md) |
| ECS service cannot stay healthy | [App Service Unhealthy](app-service-unhealthy.md) |
| Roll back an app image without data changes | [ECS Deploy Rollback](ecs-deploy-rollback.md) |
| RDS CPU, storage, or connection pressure | [RDS Pressure](rds-pressure.md) |
| Order event relay, consumer, or DLQ failure | [Order Event Queue Failure](order-event-queue-failure.md) |
| Scheduled export missing or failed | [Data Export Job Failure](data-export-job-failure.md) |
| Terraform/app ownership drift | [App And Infra Ownership Boundary](app-infra-ownership.md) |
| Practice reviewed infra rollback | [Infra Rollback Drill](infra-rollback-drill.md) |
| Check rollback timing expectations | [Rollback Drill SLOs](rollback-drill-slos.md) |
