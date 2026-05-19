# Application Core And Adapters

`packages/` contains reusable behavior shared by workload examples.

- `domain/`: pure domain concepts and events
- `application/`: use cases, contracts, and workflow logic
- `infrastructure/`: concrete adapters for SQL, Dapr, storage, and runtime IO

The intent is:

- `packages/` says what the workload does and how it talks to abstractions
- `apps/` says how one concrete workload process is started and wired

Example: order events

- `packages/application/order_event_processing.py` defines the application-level
  relay and receipt workflows
- `packages/infrastructure/dapr/pubsub.py` implements the Dapr HTTP adapter
- `apps/order_event_consumer/` hosts the HTTP service and background relay
  process that wires those pieces together
