# Platform

`platform/` owns shared platform-facing artifacts:

- `workloads.json`: canonical workload contract
- `platform-inventory.json`: static inventory for non-default runtime capability evidence
- `runtime-defaults.json`: active runtime targets and blessed runtime defaults
- `runtime-conformance.json`: local/CI fixture data only
- `workload.Dockerfile`: shared workload image build
- `concerns/`: shared runtime capabilities

Rule: `platform/` is part of the stable center of the repo. `workloads.json`
defines workload intent and classification. `concerns/` defines reusable shared
capabilities. `infra/`,
workflows, and scripts define runtime-target realization, delivery
choreography, and provider wiring. Do not turn `workloads.json` into a
deployment DSL. Keep workload owner, supported runtimes, and admitted runtimes
explicit in the contract.

Examples should consume the platform contract and catalog instead of bypassing
them, but real workloads still belong in `apps/` even when they support only
local runtime targets such as `local-compose` or `local-kubernetes`. AWS
admission is a separate runtime decision. Full runtime admission still requires
contract shape, local proof, runtime realization, delivery path, and owner.
