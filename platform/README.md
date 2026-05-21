# Platform

`platform/` owns shared platform-facing artifacts:

- `workloads.json`: canonical workload contract
- `platform-inventory.json`: canonical static platform inventory for current runtime and adapter seams
- `runtime-conformance.json`: local/CI fixture data only
- `workload.Dockerfile`: shared workload image build
- `concerns/`: shared runtime capabilities

Rule: `platform/` is part of the stable center of the repo. `workloads.json`
defines workload intent. `concerns/` defines reusable shared capabilities.
`infra/`, workflows, and scripts define runtime-target realization, delivery
choreography, and provider wiring. Do not turn `workloads.json` into a
deployment DSL.
