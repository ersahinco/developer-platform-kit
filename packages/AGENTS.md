# packages/ — Domain, Application, and Infrastructure Rules

Scoped rules for `packages/domain/`, `packages/application/`, and `packages/infrastructure/`.
The cross-tool base rules in root `AGENTS.md` apply here too.

---

## Dependency Direction — Absolute

```
packages/domain/          ← no imports from application, infrastructure, apps, or providers
packages/application/     ← imports domain only; defines ports (interfaces)
packages/infrastructure/  ← imports application + domain; implements ports
```

If you find yourself importing outward (domain importing application, or application
importing infrastructure), stop and invert the dependency through a port.

---

## packages/domain/ — What Belongs Here

- Entities with identity and lifecycle (protect meaningful state transitions)
- Value objects: immutable, self-validating, compared by value
- Domain events: meaningful past-tense business facts (`OrderPlaced`, not `FieldChanged`)
- Domain service interfaces for operations that span multiple domain objects
- The ubiquitous language from `docs/ubiquitous-language.md` — one concept, one term

**Hard constraints:** zero imports from SQLAlchemy, FastAPI, Dapr, boto3, httpx,
or any provider SDK. No `Settings` classes. No environment variable reads.

---

## packages/application/ — What Belongs Here

- Use cases: load aggregate via port → invoke domain behavior → persist via port → publish event
- Port interfaces (abstract base classes) that `packages/infrastructure/` implements
- Workflow logic that coordinates domain objects without owning business decisions

**Hard constraints:** no SQL, no Dapr component calls, no AWS SDK, no FastAPI
request/response types. Use cases must not instantiate infrastructure directly.

---

## packages/infrastructure/ — What Belongs Here

- SQLAlchemy repositories: implement ports, return domain objects (not ORM rows)
- Dapr pub/sub adapter: translate between domain events and Dapr CloudEvents
- S3 adapter, external HTTP clients, and all provider SDK usage
- Keep adapters humble — translate formats, do not own business decisions

**Hard constraint:** business rules stay out of repository implementations.

---

## Aggregate Design

- Small aggregates: one root, minimal internal state
- Route all invariant-changing behavior through the aggregate root
- Reference other aggregates by identity only — never by object reference
- One aggregate per transaction by default; use domain events for eventual consistency

---

## Naming

- Name files after the domain concept: `order_repository.py` not `sql_repository.py`
- Same domain name across layers is correct and expected:
  - `packages/application/data_export.py` → export use case
  - `packages/infrastructure/data_export.py` → SQL/file/S3 adapters
- Use the ubiquitous language from `docs/ubiquitous-language.md`

---

## Testing

- Domain and application tests run without real database, Dapr, or AWS — use fakes for all ports
- Infrastructure adapter tests live in `tests/infrastructure/` and may use real local dependencies
- Do not let test convenience force leaky interfaces or expose domain internals
