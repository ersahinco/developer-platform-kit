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

Future enterprise connectivity such as VPN, Direct Connect, PrivateLink,
egress proxy, firewall policy, or service mesh remains a candidate runtime
choice until an owner and conformance path exist.
