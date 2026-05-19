# aws-sdlc-containers

`aws-sdlc-containers` is an opinionated cloud-native platform monorepo seed
that standardizes how teams build, observe, containerize, and deploy portable
application workloads using proven industry-standard tools.

Short form: standardize the delivery workflow, do not replace the tools.

The repo currently keeps one intentional AWS/ECS reference runtime and a small
set of reference workloads. The reusable part is the platform contract:
workload shape, package boundaries, container builds, config and secrets,
observability, CI gates, rollout safety, and operator evidence.

## Toolkit Charter

- Use established tools directly: Docker/OCI, FastAPI, SQLAlchemy, Liquibase,
  Dapr, OpenTelemetry, Prometheus, Loki, Tempo, Grafana, Terraform, GitHub
  Actions, Trivy, Semgrep, Gitleaks, Checkov, TFLint, Ruff, Pyright, pytest,
  and `uv`.
- Keep provider details at the platform edge: AWS/ECS/RDS/S3/SNS/SQS details
  live in Terraform, Dapr components, scripts, and workflows, not in domain or
  application logic.
- Prefer small explicit conventions over private abstractions.
- Add runtime targets only for a real operating need.

## Repository Layers

- Infrastructure catalog: reusable AWS building blocks and future extracted
  modules live under `infra/catalog/`.
- Platform concerns: Dapr, observability, security, policy, and networking
  concerns live under `platform/concerns/`.
- Workload examples: the current `apps/*` hosts are reference workloads that
  show how teams consume the platform contract without taking provider
  dependencies into business logic.

`platform/workloads.json` is the temporary application specification. It owns
workload intent, portable runtime expectations, and the current build/runtime
build metadata while the repository converges on a leaner single source of
truth. `platform/runtime-conformance.json` owns the local/CI fixture data used
to prove workloads satisfy that specification from the outside.

The workload spec also declares operational class so contributors do not have
to infer from examples whether something is a public edge, internal service,
scheduled job, or operator job.

## Start Here

- Canonical doc map: [docs/README.md](docs/README.md)
- Repo and boundary rationale: [docs/architecture.md](docs/architecture.md)
- Portable workload expectations: [docs/platform-contract.md](docs/platform-contract.md)
- Runtime hosts vs reusable packages: [apps/README.md](apps/README.md), [packages/README.md](packages/README.md)
- Local workflow: [docs/local-development.md](docs/local-development.md)
- AWS deployment and operations: [docs/deployment.md](docs/deployment.md)
- Current work state: [docs/roadmaps.md](docs/roadmaps.md)

## What This Demonstrates

- Safe schema rollout with expand, dual-write, backfill, switch, and contract
- Dapr as an app-facing pub/sub boundary over AWS SNS/SQS runtime plumbing
- Scheduled and one-off workload delivery using the same image and contract
- Portable observability baseline with Prometheus, Loki, Tempo, and Grafana
- Review-first app deploy and infrastructure plan/apply workflows
- Split Terraform ownership between `infra/platform` and `infra/app`

The reference workload is intentionally complex where that complexity teaches
durable platform capabilities: schema rollout, async transport boundaries,
scheduled jobs, and operator evidence.

## Architectural Defaults

- AWS-first, not multi-cloud-first
- Portability by boundary, not by a custom abstraction layer
- Dapr only where it removes workload/provider coupling
- No Kubernetes, Helm, Kustomize, or Crossplane until there is a real runtime
  need
- No new top-level directories until they fit the platform monorepo model

## Project Shape

```text
aws-sdlc-containers/
|-- apps/                # reference workload hosts
|-- packages/            # domain, application, infrastructure
|-- db/                  # Liquibase changelog and Postgres assets
|-- infra/               # catalog boundary plus platform/app assembly roots
|-- platform/            # application spec, shared image, platform concerns
|-- scripts/             # CI, release, operator, observability, data helpers
|-- tests/               # API, contract, runtime, infrastructure checks
|-- docs/
|-- compose.yaml
`-- Makefile
```

## Quick Local Path

```bash
make dev
make migrate
make seed
make local-up
curl --fail --show-error http://localhost:8000/health
```

Common checks:

```bash
uv sync --all-packages --group dev --group scripts --group test
make lint
uv run pytest tests/ -v
```

Optional local extras:

```bash
make observability
make dapr-up
```

For full local setup, use [docs/local-development.md](docs/local-development.md).

## Delivery Shape

- `app-build.yml`: validate, test, run runtime conformance, build, scan, push
- `app-deploy.yml`: migrate, deploy, verify, register support workloads,
  produce release evidence
- `infra-plan.yml` / `infra-apply.yml`: reviewed Terraform plan, separate apply
- `security.yml` and `semgrep.yml`: standard security checks

Cloud-changing jobs stay split so review happens between build/plan and
deploy/apply.

## Status

This repo aims to stay lean, but not artificially simple. The current runtime
is intentionally AWS-specific; the portable value is the workload contract and
delivery workflow.
