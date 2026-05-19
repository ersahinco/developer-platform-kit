# App Dependency Readiness Drill

Use this drill to rehearse the failure mode where the app process is alive but
cannot reach its database dependency. The expected operator signal is:

- `/health` stays `200`.
- `/ready` returns `503` with `{"database": "unavailable"}`.
- Prometheus records `/ready` 5xx responses.
- Grafana shows the readiness-failure stat increasing.
- AWS operators follow app, RDS, PgBouncer, and deployment rollback runbooks
  depending on the trigger.

The drill should be run in a local development environment unless an incident
commander explicitly schedules the AWS variant.

Use Terraform outputs and environment variables for the AWS variant:

```bash
export AWS_REGION="${AWS_REGION:-eu-central-1}"
export STACK_NAME="${STACK_NAME:-<stack-name>}"
```

## Local Trigger

Start the local stack and optional observability:

```bash
make dev
make migrate
docker compose build app
docker compose up -d app
make observability
```

Confirm the healthy baseline:

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/ready
curl -fsS http://localhost:8000/metrics | rg 'http_requests_total.*route="/ready"'
```

Trigger dependency-readiness failure by stopping PgBouncer while leaving the app
container running:

```bash
docker compose stop pgbouncer
```

Generate a few readiness probes:

```bash
for i in 1 2 3; do curl -i http://localhost:8000/ready; done
curl -i http://localhost:8000/health
```

## Expected Symptoms

The readiness endpoint should fail while liveness remains healthy:

```bash
curl -i http://localhost:8000/ready
curl -i http://localhost:8000/health
```

The `/ready` response should be `503` and include:

```json
{"status":"unready","checks":{"database":"unavailable"}}
```

The `/health` response should remain `200`:

```json
{"status":"ok"}
```

Prometheus should expose a counter for the failed readiness probes:

```bash
curl -fsS http://localhost:8000/metrics | rg 'http_requests_total.*route="/ready".*status_code="503"'
```

Grafana's `AWS SDLC Containers / App Overview` dashboard should show the
readiness-failure stat increasing. Loki should show the corresponding `/ready`
requests in local app logs.

## Investigation

Check whether the process is alive but dependency readiness is failing:

```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8000/ready
docker compose ps app pgbouncer db
docker compose logs --tail=100 app
docker compose logs --tail=100 pgbouncer
docker compose logs --tail=100 db
```

For an AWS incident with the same symptoms, use the same split:

```bash
curl -i "https://$(terraform -chdir=infra/app output -raw api_fqdn)/health"
curl -i "https://$(terraform -chdir=infra/app output -raw api_fqdn)/ready"
aws logs tail "/ecs/${STACK_NAME}/app" --since 30m --region "$AWS_REGION"
aws ecs describe-services \
  --cluster "$(terraform -chdir=infra/app output -raw ecs_cluster_name)" \
  --services "$(terraform -chdir=infra/app output -raw app_service_name)" \
  --region "$AWS_REGION"
aws rds describe-db-instances --region "$AWS_REGION"
```

Then choose the owning runbook:

- If ALB targets are unhealthy, the app cannot serve `/health`, or edge alarms
  are firing, use [App Service Incident](../runbooks/app-service-incident.md).
- If the app serves `/health` but database-backed readiness or requests fail,
  use [RDS Pressure](../runbooks/rds-pressure.md).
- If the symptom started immediately after a deploy, use
  [ECS Deploy Rollback](../runbooks/ecs-deploy-rollback.md) after confirming
  the previous task definition was healthy.

## Recovery

For the local drill, restart PgBouncer:

```bash
docker compose up -d pgbouncer
```

Confirm readiness recovers:

```bash
curl -fsS http://localhost:8000/ready
curl -fsS http://localhost:8000/metrics | rg 'http_requests_total.*route="/ready"'
```

For AWS, apply the recovery path from the selected runbook. Do not roll back
the app solely because `/ready` fails; first identify whether the failing
dependency is RDS connectivity, PgBouncer, security groups, credentials, or a
new task definition.

## Success Criteria

- The team can explain why `/health` stayed healthy while `/ready` failed.
- The failing dependency is visible from endpoint responses, logs, and metrics.
- The Grafana readiness-failure stat moves during the drill.
- Recovery restores `/ready` to `200`.
- The chosen AWS runbook matches the observed ownership boundary.
