# Platform

`platform/` owns shared platform-facing artifacts:

- `workloads.json`: temporary application specification
- `runtime-conformance.json`: local/CI fixture data only
- `workload.Dockerfile`: shared workload image build
- `concerns/`: shared runtime capabilities

Rule: `workloads.json` defines workload intent. `infra/`, workflows, and
scripts define delivery choreography and provider wiring. Do not turn
`workloads.json` into a deployment DSL.
