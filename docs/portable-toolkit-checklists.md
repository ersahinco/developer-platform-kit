# Portable Toolkit Checklists

These checklists turn the repo into a lean platform-like toolkit without adding
another runtime before there is a real need. They are intentionally small:
standard app surfaces, standard delivery checks, standard observability, and
provider-specific details kept at platform edges.

## New Workload

Use this when adding a service, worker, scheduled job, or one-off job:

- Add `apps/<name>/main.py`, `apps/<name>/pyproject.toml`, and
  `apps/<name>/Dockerfile`.
- Add the workload to `platform/workloads.json`.
- For services, expose `/health`, `/ready`, and `/metrics`.
- For jobs, emit structured start, progress, success, and failure events and
  document idempotency.
- Declare env vars, secret names, rollback category, and release evidence.
- Keep business behavior in `packages/domain` and `packages/application`.
- Keep SQL, Dapr, object storage, and provider adapters in
  `packages/infrastructure`.
- Add focused tests before adding runtime infrastructure.

## Dapr Eventing

Dapr is the portable application-facing event boundary. App code should depend
on Dapr pub/sub names, topics, outbox state, and HTTP sidecar semantics, not on
SNS, SQS, Service Bus, Pub/Sub, Kafka, or Redis APIs.

- Keep provider pub/sub components under runtime-owned Dapr manifests and
  Terraform.
- Keep the durable outbox in PostgreSQL unless a deliberate data ownership
  change is made.
- Preserve stable event names, event IDs, structured logs, and retry evidence.
- Let each runtime implement the Dapr component with the provider service that
  fits its cost and reliability needs.

## Config And Secrets

- Use descriptive env names that express application intent.
- Use provider-specific resource names only at platform/delivery edges.
- Inject secrets through the runtime secret mechanism.
- Never bake secrets into images, logs, release artifacts, or plaintext
  Terraform variables.
- Prefer full URLs for local and test ergonomics; allow composed host/user/name
  plus secret password for runtime deployment.
- Document new config in `platform/workloads.json` before wiring provider
  infrastructure.

## Observability Onboarding

Every workload should be useful in the OSS observability stack:

- Prometheus metrics for request counts, latency, readiness failures, job
  outcomes, and workload-specific error counts.
- Loki-compatible structured logs with `stack`, `environment`, `service`,
  `container`, and workload correlation fields.
- Optional OTLP/HTTP traces to Tempo when spans materially improve debugging.
- Grafana dashboards or panels that use Prometheus, Loki, and Tempo as the app
  baseline.
- Release evidence events for cloud-changing deploy, rollback, drill, and infra
  apply paths.

Provider-native metrics are allowed for provider-managed infrastructure. They
should explain platform symptoms, not become required app dashboards.

## CI Quality Gates

GitHub Actions is the current delivery control plane. New workloads and runtime
edges should keep these checks runnable locally and in CI:

- `uv run python scripts/ci/validate_platform_contract.py`
- `uv run pytest tests/ -v` or a narrower justified slice while iterating.
- `make lint-workflows`
- `make lint-docs`
- `make lint-dockerfiles` when Dockerfiles change.
- `make lint-scripts` when shell scripts change.
- `terraform fmt -check -recursive infra` for Terraform changes.
- Terraform validate, TFLint, and Checkov in reviewed infra workflows.
- Ruff, Pyright, secret scan, dependency audit, Semgrep, Trivy, and image scan
  in the existing local/CI split.

## Data And Object Storage

S3 is the current AWS object-storage implementation for the data hub. The
portable contract is the dataset path, manifest shape, idempotent run ID, and
write ordering:

- Write raw data before the manifest.
- Validate byte count and checksum before publishing success.
- Keep `raw/`, `curated/`, and `manifests/` prefixes stable.
- Keep provider SDK usage inside infrastructure adapters.
- Let future runtimes map the same object contract to S3, GCS, Azure Blob,
  Supabase Storage, or another object store only when needed.
