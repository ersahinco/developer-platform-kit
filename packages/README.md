# Core And Adapters

`packages/` contains reusable workload behavior.

- `domain/`: entities, value objects, domain events
- `application/`: use cases, ports, workflow logic
- `infrastructure/`: SQL, Dapr, storage, runtime adapters

Rule: `packages/` owns reusable behavior. `apps/` owns process wiring.
