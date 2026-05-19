# tests/ — Test Rules

Scoped rules for all tests under `tests/`.
The cross-tool base rules in root `AGENTS.md` apply here too.

---

## Test Layer Map

| Directory | What it tests |
|---|---|
| `tests/api/` | HTTP contract: request/response shape, status codes, error handling (full stack) |
| `tests/application/` | Use cases with fakes for all ports — no real database, Dapr, or AWS |
| `tests/apps/` | Workload host: settings loading, wiring, lifecycle |
| `tests/contracts/` | Platform contract conformance — workloads satisfy declared expectations |
| `tests/data/` | Schema, migration, export behavior |
| `tests/infrastructure/` | Adapter integration — real local database or Dapr, isolated from business logic |
| `tests/runtime/` | Runtime conformance — external proof using `platform/runtime-conformance.json` |
| `tests/scripts/` | Script behavior |

---

## Isolation Rules

- `tests/application/` must run without real database, Dapr, or AWS — fakes/stubs for all ports
- `tests/api/` runs against the full stack (compose up) — these are integration tests
- `tests/infrastructure/` may use real local dependencies — keep isolated from business logic tests
- `tests/runtime/` uses `platform/runtime-conformance.json` fixture data

Never let test convenience force leaky interfaces or expose domain internals.

---

## Property-Based Testing

Use `hypothesis` for properties that should hold across a wide range of inputs:
- Domain invariants (order total always non-negative)
- Idempotency properties (applying the same event twice produces the same state)
- Schema evolution (v1 payload readable by v2 reader)

The `.hypothesis/` directory stores learned examples — it is committed so CI benefits from prior runs.

---

## Naming and Structure

- Test file names mirror the module: `test_order.py` tests `order.py`
- Test function names describe behavior: `test_order_total_is_sum_of_line_items`
- Use `conftest.py` for shared fixtures — keep fixtures close to the tests that use them
- Shared factories in `tests/fixtures/`, shared utilities in `tests/helpers/`
- No shared mutable state between tests

---

## Running Tests

```bash
uv run pytest tests/ -v                              # full suite
uv run pytest tests/application/ -v                 # application layer only
uv run pytest tests/api/ -v                         # API contracts only
make runtime-conformance                             # external contract proof
uv run pytest tests/ --cov=packages --cov-report=term-missing  # with coverage
```
