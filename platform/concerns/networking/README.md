# Networking Concern

Shared runtime networking capability owned at the platform edge.

The workload contract declares portable needs such as exposure, service ports,
and runtime support. Runtime targets decide the concrete network machinery.

Current network defaults live in `platform/runtime-defaults.json` under
`network_connectivity`:

- `local-compose`: Docker Compose networks and explicit host ports in
  `compose.yaml`
- `local-kubernetes`: kind ClusterIP Services, probes, in-cluster DNS,
  daprd-to-app sidecar routing, Redis-backed local pub/sub, and dependency routing
  in `infra/local-kubernetes`, checked by
  `tests/contracts/test_local_kubernetes_contract.py`
- `aws-ecs`: ALB ingress, private ECS placement, VPC subnets, and security
  groups in `infra/platform/network.tf`, `infra/app/edge.tf`,
  `infra/app/compute_ecs.tf`, and `infra/app/workload_jobs.tf`

Add another connectivity mechanism only when a workload has a concrete need,
an owner, and a conformance path.
