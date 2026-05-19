# Runbooks

Use these during AWS incidents, failed deploys, and alarm investigations.
These pages own operator action only. Use canonical docs for architecture,
contract, and capability questions.

| Situation | Runbook |
|---|---|
| App health, 5xx, or latency incident | [App Service Incident](app-service-incident.md) |
| Roll back an app image without data changes | [ECS Deploy Rollback](ecs-deploy-rollback.md) |
| RDS CPU, storage, or connection pressure | [RDS Pressure](rds-pressure.md) |
| Order event relay, consumer, or DLQ failure | [Order Event Queue Failure](order-event-queue-failure.md) |
| Scheduled export missing or failed | [Data Export Job Failure](data-export-job-failure.md) |
| Terraform/app ownership drift | [App And Infra Ownership Boundary](app-infra-ownership.md) |
| Practice rollback drills and timing expectations | [Rollback Drill SLOs](rollback-drill-slos.md) |

## Operator Entry Points

Prefer these commands before diving into individual AWS consoles:

```bash
make post-deploy-verify
make incident-evidence
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id> \
make incident-evidence
make observability-delivery-verify
make release-event-delivery-verify
```

Use downloaded `release-evidence-*` artifacts from GitHub Actions whenever they
exist. They keep build, deploy, and apply evidence portable and make incident
review much easier to reconstruct later.
