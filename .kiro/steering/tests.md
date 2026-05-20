---
inclusion: fileMatch
fileMatchPattern: "tests/**/*.py"
---

# Test Rules

Activated when working in `tests/`.

## Layer Map

| Directory | Tests |
|---|---|
| `tests/api/` | Full-stack HTTP contracts |
| `tests/application/` | Use cases with fakes only |
| `tests/apps/` | Workload host wiring and lifecycle |
| `tests/contracts/` | Platform contract and repo-shape rules |
| `tests/data/` | Schema, migration, export behavior |
| `tests/infrastructure/` | Adapter integration with local dependencies |
| `tests/runtime/` | External conformance via `platform/runtime-conformance.json` |
| `tests/scripts/` | Script behavior |

## Rules

- `tests/application/` uses fakes, not real database, Dapr, or AWS.
- `tests/api/` is integration-level.
- `tests/infrastructure/` stays isolated from business logic tests.
- Use `hypothesis` for invariants, idempotency, and schema evolution.
- Test names describe behavior.
- No shared mutable state.
