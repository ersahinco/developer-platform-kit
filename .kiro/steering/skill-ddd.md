---
inclusion: manual
---

# Skill: Domain-Driven Design

Load when modeling new domain concepts, aggregates, domain events, or when
language feels fuzzy.

## Core Rule

Practical DDD is not renamed CRUD. Model one explicit bounded context with one
local language.

Current bounded context: order fulfillment and delivery platform.
Vocabulary owner: `docs/ubiquitous-language.md`.

## Rules

- Use the local ubiquitous language in code, tests, events, APIs, and docs.
- Keep aggregates small, root-protected, and invariant-driven.
- Reference other aggregates by identity only.
- Default to one aggregate per transaction; use domain events for eventual
  consistency.
- Publish meaningful past-tense business facts such as `OrderPlaced`.
- Application services coordinate use cases; they do not own business
  decisions.
- Keep FastAPI, SQLAlchemy, Dapr, and AWS types out of `packages/domain`.
- Promote meaningful primitives to value objects.
- Use domain services only for domain-significant multi-object operations.

## Triggers

- a term is ambiguous or overloaded
- vendor, API, transport, persistence, or UI shape appears in domain code
- one transaction wants multiple aggregates without a proven invariant reason
- external code mutates aggregate internals
- route handlers or application services accumulate branching business rules

## Checklist

- vocabulary matches `docs/ubiquitous-language.md`
- aggregates are small and invariant-driven
- value objects are validated and immutable
- domain events are meaningful facts
- business logic stays out of transport and infrastructure code
