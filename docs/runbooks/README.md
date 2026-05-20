# Runbooks

Use during AWS incidents, failed deploys, and drills.

Runbooks own operator action only. Shared deploy/apply review commands live in
[Deployment](../deployment.md#review-checklist). Architecture, contract, and
capability truth live in the canonical docs under [../README.md](../README.md).

| Situation | Runbook |
|---|---|
| App health, 5xx, or latency incident | [App Service Incident](app-service-incident.md) |
| Roll back an app image without data changes | [ECS Deploy Rollback](ecs-deploy-rollback.md) |
| RDS CPU, storage, or connection pressure | [RDS Pressure](rds-pressure.md) |
| Order event relay, consumer, or DLQ failure | [Order Event Queue Failure](order-event-queue-failure.md) |
| Scheduled export missing or failed | [Data Export Job Failure](data-export-job-failure.md) |
| Terraform/app ownership drift | [App And Infra Ownership Boundary](app-infra-ownership.md) |
| Practice rollback drills and timing expectations | [Rollback Drill SLOs](rollback-drill-slos.md) |
