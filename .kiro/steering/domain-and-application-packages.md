---
inclusion: fileMatch
fileMatchPattern: "packages/**/*.py"
---

# Domain and Application Package Rules

Activated when working in `packages/domain/`, `packages/application/`, or `packages/infrastructure/`.

## Dependency Rule

```text
packages/domain -> no outward imports
packages/application -> imports domain only; owns ports
packages/infrastructure -> imports application + domain; implements ports
```

## Layer Rules

- `packages/domain/`: entities, value objects, domain events, domain services. No SQLAlchemy, FastAPI, Dapr, boto3, `Settings`, or env reads.
- `packages/application/`: use cases, ports, workflow logic. No SQL, Dapr calls, AWS SDK, direct infrastructure creation, or HTTP framework types.
- `packages/infrastructure/`: repositories and runtime adapters. No business rules.

## Design Rules

- Business invariants live in domain objects.
- Use cases coordinate through ports.
- Adapters translate formats only.
- Names follow `docs/ubiquitous-language.md`.
- Domain and application tests use fakes, not real infrastructure.
