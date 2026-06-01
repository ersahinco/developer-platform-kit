# Operator Day 2 Commands

Short command sheet for operating the delivery toolkit after the first local
run. Use [Deployment](deployment.md) for workflow ownership and
[Runbooks](runbooks/README.md) for incident-specific action.

## Paved Road

Use this order when moving from local confidence to AWS operation:

1. Check the operator workstation and workload contract.
2. Run safe cloud readiness before any workflow that can change cloud state.
3. Dispatch reviewed dry runs or cloud-changing workflows from GitHub.
4. Download release evidence and operator payloads for the selected run.
5. Build incident evidence before changing state during a failure.

```bash
make platform-doctor
make platform-doctor-cloud
make workload-readiness-check
make platform-toolkit-validate-cloud
make workflow-dry-run-commands
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
GH_RUN_ID=<workflow-run-id> make operator-payload-download
LOOKBACK_MINUTES=60 make incident-evidence
```

## Workstation Readiness

`make platform-doctor` and `make platform-doctor-cloud` print the next
operator path from this page after prerequisite checks finish.

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

Use the Compose URL from inside the local runtime, or the public edge URL for a
cloud check.

```bash
INTEGRATION_CHECK_TARGETS=api=http://api:8000/health make integration-check
INTEGRATION_CHECK_TARGETS=api=https://api.<root-domain>/health make integration-check
```

## Incident Evidence

Download the matching release evidence first when the incident follows a
GitHub workflow run.

```bash
make release-evidence-runs
GH_RUN_ID=<workflow-run-id> make release-evidence-download
RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id> \
LOOKBACK_MINUTES=60 make incident-evidence
```

## Local Data Evidence

```bash
make data-export
make open-dataset-pipeline
make data-artifacts-list
make data-artifacts-shell
```
