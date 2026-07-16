# First 30 Minutes

Fast path for a new developer validating the delivery toolkit shape without
accidentally running every proof surface.

## 1. Required First Pass

Stay local and non-mutating first:

```bash
make help-local
make platform-doctor
make workload-readiness
make local-kubernetes-admission-report
```

`platform-doctor` checks local tools, Docker daemon access, repo files, and
workload readiness. It also checks the default local Compose ports and tells
you which `*_PORT` override to set before Docker fails on a bind error. Ports
needed by the first live smoke are blockers; observability-only ports are
warnings until you choose `make local-up`. GitHub auth is optional and
cloud-only tools are warnings here; they become required only in
`make platform-doctor-cloud`.

For API port conflicts, set both the Compose port and the smoke-test URL:

```bash
APP_PORT=18000 LOCAL_API_BASE_URL=http://127.0.0.1:18000 make platform-toolkit-smoke-local
```

`workload-readiness` is the maturity summary. Use
`workload-readiness-local`, `workload-readiness-cloud`, or
`local-kubernetes-admission-report` when you need a narrower view.

## 2. Add Cheap Static Proof

Run these when the first pass is clean and you want proof without starting the
full local stack:

```bash
make workload-readiness-check
make local-kubernetes-contracts
```

This proves the declared workload and local Kubernetes contract surfaces. It
does not create a kind cluster or run the app host.

## 3. Choose One Live Local Proof

For the first live app-host proof, run the smoke target by itself:

```bash
make platform-toolkit-smoke-local
```

This starts the local app and Dapr surfaces, verifies API health/readiness and
metrics, publishes through Dapr, and runs one bounded backfill batch. If this
fails on a port bind, rerun `make platform-doctor` and either stop the process
using the port or set the matching `*_PORT` override. The smoke path does not
start Prometheus, Loki, Tempo, Promtail, or Grafana; use `make local-up` after
the first pass when you need the local observability stack.

## 4. Prove The Full Local Compose Path

Use the full proof when you are validating the delivery toolkit rather than one
small app-host edit:

```bash
make platform-toolkit-validate-local
```

This starts the local runtime, applies migrations, checks API health/readiness
and metrics, publishes through Dapr, runs data jobs, emits operator evidence,
and finishes with runtime conformance.

## 5. Inspect The App Surface

```bash
make api-smoke
make dapr-smoke
```

Use `api-smoke` for `/health`, `/ready`, and `/metrics`. Use `dapr-smoke` to
publish a CloudEvent through Dapr and confirm the event consumer records it,
then invoke booking readiness through its Dapr app identity.

## 6. Inspect Local Data Artifacts

```bash
make data-export
make data-artifacts-list
```

The data export job writes raw CSV and manifest artifacts into the local
`data_exports` Docker volume.

## 7. Use Local Kubernetes When Compose Is Too Small

Local Kubernetes is an active local proof runtime target, not a production
Kubernetes claim. Use it when you need Services, probes, Jobs, ConfigMaps,
Secrets, service identity, rollout/rollback, Dapr sidecar wiring, endpoints,
logs, or events:

```bash
make workload-readiness-local
make local-kubernetes-contracts
make local-kubernetes-evidence-drill
```

Start with `local-kubernetes-admission-report` when you only need to understand
which workloads are ready for that proof surface.

## 8. Walk The Schema Rollout Shape

```bash
make backfill-once
```

This runs one bounded local backfill batch. Use it with
[Local Development](local-development.md#migration-rollout-walkthrough) when
walking the expand, dual-write, backfill, switch, and contract path.

## 9. Check Safe Cloud Readiness

```bash
make workload-readiness-cloud
make platform-doctor-cloud
make platform-toolkit-validate-cloud
make workflow-dry-run-commands
```

These commands do not mutate AWS. They validate local/cloud operator
prerequisites, local security checks, workflow shape, platform policy,
contract/script behavior, Terraform syntax without remote backends, and the
generated GitHub workflow dry-run dispatch commands. `workload-readiness-cloud`
also shows the policy/delivery gate, structured log contract, secret injection
proof, delivery workflow, evidence artifact, log group, and rollback proof
category for each workload. `platform-toolkit-validate-cloud` runs
`security-readiness`, local Terraform readiness, and workflow dry-run
validation checks; use `workflow-dry-run-commands` when you want the copy-ready
`gh workflow run` commands.

Use the real cloud-changing workflows only after review, immutable image
selection, and the confirmation inputs described in
[Deployment](deployment.md).
