# Dapr Concern

This concern owns the app-facing Dapr contract for the repository.

- `profiles/local/`: local component mappings and config
- `profiles/production/`: production-facing component mappings and config

Application code can know Dapr app ids and building-block APIs such as service
invocation, pub/sub names, topics, CloudEvents, and resiliency semantics.
Provider-specific component details stay at the platform edge.

The local profile intentionally uses a simple Redis-backed pub/sub component so
the app-facing contract can be exercised without inheriting AWS broker shape.
Production keeps the current runtime-target realization at the platform edge.
Local Compose proves pub/sub through the event consumer and service invocation
through the booking workload. Local Kubernetes currently proves the pub/sub
boundary with a static event-consumer Deployment, daprd sidecar, Redis Service,
and `make local-kubernetes-evidence-drill`.

Keep Dapr as a first-class platform concern as workload complexity grows. The
goal is to standardize portable app-facing building blocks, not to hide Dapr
behind custom repository-specific abstractions.
