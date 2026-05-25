# Core And Adapters

`packages/` contains reusable workload behavior.

- `domain/`: entities, value objects, domain events
- `application/`: use cases, ports, workflow logic
- `infrastructure/`: SQL, Dapr, storage, runtime adapters

Rule: `packages/` owns reusable behavior. `apps/` owns process wiring.

Adapter rule:

- keep provider/runtime SDK usage in `packages/infrastructure/` or the platform edge
- keep domain and application centered on ports and intent, not current AWS realization details
- add future runtime adapters at the same seam instead of rewriting workload behavior
