---
inclusion: manual
---

# Skill: Clean Architecture

Load when changing `packages/`, `apps/`, or the boundary between them.

## Core Rule

Do not let details become the architecture. Business policy stays independent;
dependencies point inward.

## Rules

- `packages/domain` and `packages/application` must not import frameworks,
  databases, queues, SDKs, or runtime details.
- Put invariants in domain objects and orchestration in focused use cases.
- Pass plain request and response models across use-case boundaries.
- Treat FastAPI, SQLAlchemy, Dapr, boto3, and provider SDKs as outer details
  behind ports and adapters in `packages/infrastructure`.
- Inner layers own ports; `packages/infrastructure` implements them.
- Wiring belongs in `apps/*/`.
- Adapters translate formats only; they do not own business decisions.
- Organize by use case or business capability, not generic technical buckets.
- Test domain and application code without real database, Dapr, or AWS.

## Triggers

- framework or SDK types enter `packages/domain` or `packages/application`
- a use case instantiates SQLAlchemy, Dapr, or boto3 directly
- a route handler or Dapr subscriber owns business branching
- a shared utility becomes an escape hatch for misplaced logic
- business-rule tests require real infrastructure

## Checklist

- business rules independent from FastAPI, SQLAlchemy, Dapr, and AWS
- dependencies point inward
- domain objects guard invariants
- route handlers and adapters stay humble
- core tests run fast without real infrastructure
