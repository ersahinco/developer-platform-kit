---
inclusion: fileMatch
fileMatchPattern: "packages/**/*.py"
---

# Domain and Application Package Rules

Activated when working in `packages/domain/`, `packages/application/`, or `packages/infrastructure/`.

These rules enforce the Clean Architecture dependency rule and DDD tactical patterns
as they apply to this repo's package structure.

---

## packages/domain — Absolute Constraints

- Contains only pure entities, value objects, domain events, and domain service interfaces
- Zero imports from `packages/infrastructure`, `packages/application`, `apps/`, or any provider SDK
- No SQLAlchemy models, no Dapr types, no FastAPI types, no AWS SDK, no `boto3`, no `httpx` for outbound calls
- No environment variable reads, no `Settings` classes, no config loading
- Business invariants live here — enforce them in constructors and methods, not in callers
- Use the ubiquitous language from `docs/ubiquitous-language.md` for all names

**Trigger**: If you find yourself importing anything from outside `packages/domain/` into a domain file, stop and move the dependency outward.

---

## packages/application — Constraints

- Contains use cases, ports (abstract interfaces), and workflow logic
- May import from `packages/domain/` only
- Defines the interfaces (ports) that `packages/infrastructure/` implements — never the reverse
- No SQL, no Dapr component calls, no AWS SDK, no direct HTTP client calls to external services
- No FastAPI route handlers, no HTTP request/response types
- Use cases coordinate: load aggregate via port → invoke domain behavior → persist via port → publish event via port
- Application services must not own business decisions — those belong in domain objects

**Trigger**: If a use case directly instantiates a SQLAlchemy session, Dapr client, or boto3 resource, introduce a port and move the concrete detail to `packages/infrastructure/`.

---

## packages/infrastructure — Constraints

- Contains concrete adapters: SQLAlchemy repositories, Dapr pub/sub adapter, S3 adapter, runtime IO
- Implements ports defined in `packages/application/`
- May import from `packages/application/` and `packages/domain/`
- Must not contain business rules or domain decisions
- Keep adapters humble: translate external formats to domain calls and back, nothing more
- SQL queries, Dapr component names, S3 bucket references, and provider SDK calls belong here — not in application or domain

**Trigger**: If infrastructure code contains an `if` branch that encodes a business rule, move the rule into the domain or application layer.

---

## Naming and Structure

- Name files after the domain concept they serve, not the technical pattern: `order_repository.py` not `sql_repository.py`
- Similarly named files across layers are expected and correct when they represent different layers:
  - `packages/application/data_export.py` → export use case and workflow
  - `packages/infrastructure/data_export.py` → SQL/file/S3 adapters for that use case
- One concept gets one term inside a bounded context — use the term from `docs/ubiquitous-language.md`

---

## Testing Rules for Packages

- Test domain behavior through public methods without any real database, Dapr, or AWS
- Test application use cases with fakes/stubs for all ports — no real infrastructure
- Test infrastructure adapters separately at the seam (integration tests in `tests/infrastructure/`)
- Do not let test convenience force leaky interfaces or expose internals

---

## Aggregate Design (when adding or changing domain aggregates)

- Keep aggregates small — one root, minimal internal state
- Route all invariant-changing behavior through the aggregate root
- Reference other aggregates by identity only, never by object reference
- Default to one aggregate per transaction; use domain events for eventual consistency across aggregates
- Publish domain events only for meaningful completed business facts — not for every field change

---

## Final Check Before Committing Package Changes

- [ ] Dependency direction is inward — no domain/application code imports infrastructure or provider details
- [ ] Business rules live in domain objects, not in use cases, repositories, or adapters
- [ ] Ports (interfaces) are owned by `packages/application/`, implementations are in `packages/infrastructure/`
- [ ] Names match the ubiquitous language in `docs/ubiquitous-language.md`
- [ ] Tests for domain and application layers run without real database, Dapr, or AWS
