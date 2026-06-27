# Workload Or Capability Admission

Use this template for PRs that admit a workload or bounded platform capability.
Keep the PR in contract language first. AWS-shaped context such as ECS, IAM,
subnets, buckets, queues, or schedulers must map to an admitted workload or
bounded capability; runtime-specific resources belong only in the runtime
realization layer.

## Admission Outcome

- Request issue:
- Workload or capability:
- Owning team:
- Outcome:
  - [ ] Add local-first workload
  - [ ] Promote workload to `local-kubernetes`
  - [ ] Promote workload to `aws-ecs`
  - [ ] Add object artifact sink
  - [ ] Add operator job execution
  - [ ] Add scheduled job execution
  - [ ] Add Dapr pub/sub boundary
  - [ ] Grant bounded dependency access

## Contract

- `platform/workloads.json` change:
- Operational class:
- `runtime.supported`:
- `runtime.admitted`:
- Config env names:
- Secret names:
- Bounded dependencies, if any:
  - name/kind/purpose:
  - direction:
  - owner:
  - declared config env/secret names:
  - evidence:
- Health/readiness/metrics or job evidence:

## Runtime Realization

- Runtime target:
- Runtime files changed:
- Catalog entry used or added:
- Provider details kept out of app/domain/application code:
  - [ ] Yes

## Proof

- [ ] `make workload-readiness`
- [ ] `make workload-readiness-check`
- [ ] `make runtime-conformance`
- [ ] `uv run pytest tests/contracts -q`
- [ ] Runtime-specific proof command:

## Guardrails

- [ ] This does not turn `platform/workloads.json` into a deployment DSL.
- [ ] This does not add arbitrary AWS resource vending or per-team Terraform.
- [ ] AWS-shaped asks have been translated into workload or capability outcomes.
- [ ] This does not add a portal, generator, Helm/CRD layer, or new runtime target.
- [ ] Cloud admission has owner, evidence, delivery path, and operator notes.
