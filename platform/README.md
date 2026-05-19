# Platform

`platform/` owns shared platform-facing artifacts for this repository.

- `workloads.json`: the temporary application specification
- `runtime-conformance.json`: local/CI runtime fixture data for container
  conformance checks
- `workload.Dockerfile`: the shared workload image build
- `concerns/`: shared runtime capabilities and environment profiles

Keep provider implementation details in `infra/`, workflows, and scripts rather
than leaking them into workload business behavior.

Ownership rule:

- `workloads.json` owns workload intent, operational class, and the minimum
  shared image metadata needed to build and identify workloads consistently
- `runtime-conformance.json` owns local/CI fixture values only
- workflows, scripts, and `infra/` own delivery choreography, cloud rollout
  sequence, task registration, alarms, and provider wiring

Do not grow `workloads.json` into a custom deployment DSL. If a field only
describes one runtime's rollout choreography, it belongs at the delivery edge
instead.
