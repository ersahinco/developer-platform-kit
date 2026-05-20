---
inclusion: fileMatch
fileMatchPattern: "tests/**/*.py"
---

# Test Rules

Activated when working in `tests/`.

---

## Test Layer Map

| Directory | Tests |
|---|---|
| `tests/api/` | HTTP contract tests against the running API — request/response shape, status codes, error handling |
| `tests/application/` | Use case tests with fakes/stubs for all ports — no real database, Dapr, or AWS |
| `tests/apps/` | Workload host integration tests — settings loading, wiring, lifecycle |
| `tests/contracts/` | Contract conformance tests — verify workloads satisfy the platform contract |
| `tests/data/` | Data layer tests — schema, migration, export behavior |
| `tests/infrastructure/` | Adapter integration tests — real database or real Dapr, isolated from business logic |
| `tests/runtime/` | Runtime conformance tests — external proof that workloads satisfy `platform/workloads.json` |
| `tests/scripts/` | Script behavior tests |

---

## Test Isolation Rules

- `tests/application/` tests must run without a real database, Dapr, or AWS — use fakes or stubs for all ports
- `tests/api/` tests run against the full stack (compose up) — they are integration tests, not unit tests
- `tests/infrastructure/` tests may use a real database (local compose) — keep them isolated from business logic tests
- `tests/runtime/` tests use `platform/runtime-conformance.json` fixture data — they prove the contract from the outside

Never let test convenience force leaky interfaces or expose domain internals.

---

## What to Test

- Domain behavior: aggregate invariants, valid and invalid state transitions, value object validation
- Application use cases: happy path, failure paths, port interactions
- API contracts: request/response shape, status codes, error bodies, auth behavior
- Runtime conformance: health, readiness, metrics endpoints, structured log labels
- Infrastructure adapters: at the seam — test the adapter, not the business rule

---

## Property-Based Testing

Use `hypothesis` for properties that should hold across a wide range of inputs:
- Domain invariants (e.g., an order total is always non-negative)
- Idempotency properties (e.g., applying the same event twice produces the same state)
- Schema evolution properties (e.g., a v1 payload can always be read by a v2 reader)

The `.hypothesis/` directory stores learned examples — commit it so CI benefits from prior runs.

---

## Test Naming and Structure

- Test file names mirror the module they test: `test_order.py` tests `order.py`
- Test function names describe behavior: `test_order_total_is_sum_of_line_items` not `test_order_1`
- Use `conftest.py` for shared fixtures — keep fixtures close to the tests that use them
- Prefer explicit fixtures over implicit global state

---

## Fixtures and Factories

- Use `tests/fixtures/` for shared test data factories
- Use `tests/helpers/` for shared test utilities
- Keep fixture data minimal — only what the test needs
- Do not share mutable state between tests

---

## Running Tests

```bash
# Full suite
uv run pytest tests/ -v

# Specific layer
uv run pytest tests/application/ -v
uv run pytest tests/api/ -v

# Runtime conformance (requires compose up)
make runtime-conformance

# With coverage
uv run pytest tests/ --cov=packages --cov-report=term-missing
```

---

## Final Check Before Committing Test Changes

- [ ] Application tests run without real database, Dapr, or AWS
- [ ] New behavior has a test — happy path and at least one failure path
- [ ] Test names describe behavior, not implementation
- [ ] `make runtime-conformance` passes
- [ ] No test relies on execution order or shared mutable state
