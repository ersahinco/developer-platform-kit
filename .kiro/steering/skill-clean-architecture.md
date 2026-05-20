---
inclusion: manual
---

# Skill: Clean Architecture (Robert C. Martin)

Load this when: adding, changing, reviewing, or refactoring code whose business rules should survive changes in frameworks, databases, delivery mechanisms, or schedule pressure.

In this repo that means: any change to `packages/`, `apps/`, or the boundary between them.

---

## Primary Bias to Correct

Do not let details become the architecture. Business policy stays independent, dependencies point inward, and volatile mechanisms remain replaceable.

---

## Decision Rules

- Source dependencies must point inward toward higher-level policy. `packages/domain` and `packages/application` must not import frameworks, databases, web handlers, queues, external service clients, or other details.
- Put enterprise rules and invariants in domain objects; put application-specific orchestration in focused use cases in `packages/application/`.
- Pass plain request and response models across use-case boundaries. Do not pass FastAPI `Request` objects, SQLAlchemy rows, or Dapr response types into or out of `packages/application/`.
- Treat FastAPI, SQLAlchemy, Dapr, boto3, and all provider SDKs as outer-layer details behind ports, gateways, or adapters in `packages/infrastructure/`.
- Inner layers own the interfaces (ports) they need; `packages/infrastructure/` implements them. Concrete wiring belongs in `apps/*/` composition roots.
- Keep adapters humble. HTTP route handlers, Dapr pub/sub adapters, S3 adapters, and SQL repositories translate external formats to use-case calls and back — they do not own business decisions.
- Organize by use case or business capability, not by generic technical buckets. The structure should reveal domain intent.
- Test domain objects and use cases first, without real database, Dapr, or AWS. Test adapters separately at the seam.
- Preserve behavior while improving dependency direction. Prefer incremental boundary extraction over rewrites.

## Trigger Rules

- When framework annotations, ORM rows, Dapr types, or AWS SDK types enter `packages/domain/` or `packages/application/`, move translation outward to `packages/infrastructure/`.
- When a use case directly instantiates a SQLAlchemy session, Dapr client, or boto3 resource, introduce a port.
- When an HTTP route handler or Dapr subscriber contains business branching or validation, move the rule into `packages/application/` or `packages/domain/`.
- When a `*Service`, utility folder, or shared module becomes an escape hatch for misplaced logic, split by use case and restore dependency direction.
- When tests need a real database or Dapr to verify business rules, move tests to use cases with fakes.

## Final Checklist

- [ ] Business rules independent from FastAPI, SQLAlchemy, Dapr, and AWS?
- [ ] Dependencies point inward — ports owned by `packages/application/`, implementations in `packages/infrastructure/`?
- [ ] Domain objects guard invariants; use cases orchestrate one application action?
- [ ] Route handlers, Dapr adapters, and SQL repositories are humble?
- [ ] Core tests run fast without real database, Dapr, or AWS?
- [ ] Details remain replaceable without rewriting business rules?
