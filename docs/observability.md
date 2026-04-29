# Observability Plan

Prometheus, Loki, and Grafana are the preferred observability target for this
project. CloudWatch remains a useful AWS-native tradeoff, but it is not the
primary demo path.

## Current State

- Application health endpoint exists.
- Application metrics endpoint exists at `/metrics`.
- App and task logs are emitted through ECS and Docker.
- Terraform creates CloudWatch log groups for ECS workloads.
- Local Prometheus, Loki, Promtail, and Grafana run through the optional
  `observability` Docker Compose profile.

## Local Stack

Start the app first, then start the observability profile:

```bash
docker compose build app
docker compose up -d app
make observability
```

Open:

| Tool | URL |
|---|---|
| App metrics | `http://localhost:8000/metrics` |
| Prometheus | `http://localhost:9090` |
| Loki | `http://localhost:3100/ready` |
| Grafana | `http://localhost:3000` |

Grafana credentials default to `admin` / `admin` and can be overridden through
`.env`. The provisioned dashboard is `AWS SDLC Containers / App Overview`.

The local stack contains:

- Prometheus scraping the app `/metrics` endpoint.
- Loki storing local container logs.
- Promtail reading Docker container logs through the Docker socket.
- Grafana data sources and dashboard provisioning.

Promtail requires read-only access to `/var/run/docker.sock`, so the
observability profile is opt-in and not started by default.

## AWS Extension

After the local stack works, decide whether to deploy observability to AWS:

- Prometheus/Loki/Grafana on ECS for open-source control.
- Amazon Managed Grafana plus CloudWatch for lower operational overhead.
- CloudWatch-only for the smallest AWS footprint.

The default implementation path remains local Prometheus, Loki, and Grafana
first.

## Acceptance Criteria

- Prometheus target is healthy.
- Grafana dashboard loads from provisioning.
- Loki shows app logs.
- `/metrics` does not change `/health` or API behavior.
- Observability remains optional for the base app rollout.
