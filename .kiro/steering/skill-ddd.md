---
inclusion: manual
---

# Skill: Domain-Driven Design (Vaughn Vernon — IDDD + DDD Distilled)

Load this when: modeling new domain concepts, adding aggregates, designing domain events, mapping bounded context integrations, or when language in the code feels fuzzy or overloaded.

---

## Primary Bias to Correct

Practical DDD is not renamed CRUD. Model the operational domain inside an explicit Bounded Context, with local language, small invariant boundaries, identity references across aggregates, and explicit translation across context and infrastructure boundaries.

---

## This Repo's Bounded Context

The current codebase represents a single bounded context: the **order fulfillment and delivery platform**. The ubiquitous language is defined in `docs/ubiquitous-language.md`. Use it consistently — one concept gets one term, one term does not carry multiple meanings.

---

## Decision Rules

- Use the local ubiquitous language in code, tests, commands, domain events, APIs, and conversations. Rename when understanding improves.
- Keep aggregates small: one root, minimal internal state, invariant-driven boundaries.
- Route all invariant-changing behavior through the aggregate root. Hide mutable internals.
- Reference other aggregates by identity only — never by object reference.
- Default to one aggregate per transaction. Use domain events for eventual consistency across aggregates.
- Publish domain events only for meaningful completed business facts in past tense (`OrderPlaced`, `BackfillCompleted`). Do not publish events for every field change.
- Application services in `packages/application/` coordinate use cases: load aggregate via port → invoke domain behavior → persist via port → publish event. They must not own business decisions.
- Keep FastAPI, SQLAlchemy, Dapr, and AWS types out of `packages/domain/`. Translate at the boundary.
- Use value objects for meaningful descriptive concepts — validate at construction, compare by value, replace raw primitives for meaningful identifiers, quantities, and ranges.
- Use domain services only for domain-significant operations that require multiple domain objects and fit no entity or value object.

## Trigger Rules

- When a term is ambiguous, reused across concerns, or drifting into a technical placeholder, qualify or rename it before coding further.
- When legacy, vendor, API, transport, persistence, or UI shape appears in `packages/domain/`, add a mapping boundary before modeling locally.
- When an aggregate boundary changes or one transaction wants multiple aggregates, list the immediate invariants that require it; otherwise coordinate by identity, domain events, or application services.
- When external code mutates aggregate internals or reads internals to decide state changes, move the operation behind root behavior.
- When application services or route handlers accumulate branching business rules, move the decision into the entity, value object, or aggregate that owns the concept.
- When a concept is represented as a primitive, flag, status code, or boolean but carries domain rules, promote it to a richer concept or value object.

## Final Checklist

- [ ] Ubiquitous language visible in code, tests, events, APIs, and conversations — matches `docs/ubiquitous-language.md`?
- [ ] Aggregates small, root-protected, invariant-driven, identity-linked, and usually one per transaction?
- [ ] Entities are behavior-bearing; value objects are immutable, validated, and value-equal?
- [ ] Domain events are meaningful past-tense facts — not command-like or trivial field changes?
- [ ] Application services coordinate rather than own business logic?
- [ ] Infrastructure, persistence, REST, and transport details kept out of `packages/domain/`?
