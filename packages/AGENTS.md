# packages/ Rules

Root `AGENTS.md` applies here too.

## Dependency Rule

```text
packages/domain -> no outward imports
packages/application -> imports domain only; owns ports
packages/infrastructure -> imports application + domain; implements ports
```

If code imports outward, stop and invert through a port.

## Layer Rules

- `packages/domain/`: entities, value objects, domain events, domain services. No SQLAlchemy, FastAPI, Dapr, boto3, `Settings`, or env reads.
- `packages/application/`: use cases, ports, workflow logic. No SQL, Dapr calls, AWS SDK, or FastAPI types.
- `packages/infrastructure/`: repositories, Dapr adapters, S3 and HTTP clients, provider SDK usage. No business rules.
- Future runtime replacements should prefer adding or swapping infrastructure adapters and platform-edge realization code before changing domain or application behavior.

## Design Rules

- Business invariants live in domain objects.
- Ports are owned by `packages/application/`.
- Repositories return domain objects, not ORM rows.
- Same domain name across layers is fine when the layer meaning differs.
- Use the ubiquitous language from `docs/ubiquitous-language.md`.
- Treat `packages/infrastructure/` as the first adapter seam for database, pub/sub, object storage, and HTTP client portability.

## Testing

- Domain and application tests use fakes, not real database, Dapr, or AWS.
- Infrastructure adapter tests live in `tests/infrastructure/`.
- Do not leak domain internals for test convenience.
