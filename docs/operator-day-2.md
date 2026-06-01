# Operator Day 2 Commands

Short command sheet for operating the delivery toolkit after the first local
run. Use [Deployment](deployment.md) for workflow ownership and
[Runbooks](runbooks/README.md) for incident-specific action.

## Workstation Readiness

```bash
make platform-doctor
make platform-doctor-cloud
make workload-readiness
make workload-readiness-check
```

## Safe Readiness

```bash
make platform-toolkit-validate-cloud
make infra-validate-local
make workflow-dry-run-validate-gh
make workflow-dry-run-commands
```

## Deploy Observation

```bash
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
make post-deploy-verify
make observability-delivery-verify
make release-event-delivery-verify
```

## Operator Jobs

```bash
make operational-snapshot-dry-run
make operational-snapshot-cloud
GH_RUN_ID=<workflow-run-id> make operator-payload-download
```

## Integration Checks

```bash
INTEGRATION_CHECK_TARGETS=api=https://api.<root-domain>/health make integration-check
INTEGRATION_CHECK_TARGETS=api=http://api:8000/health make integration-check
```

## Incident Evidence

```bash
SERVICE_NAME=api LOOKBACK_MINUTES=60 make incident-evidence
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
```

## Local Data Evidence

```bash
make data-export
make open-dataset-pipeline
make data-artifacts-list
make data-artifacts-shell
```
