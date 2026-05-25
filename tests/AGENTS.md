# tests/ Rules

Root `AGENTS.md` applies here too.

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

- `tests/application/` runs without real database, Dapr, or AWS.
- `tests/api/` is integration-level.
- `tests/infrastructure/` stays isolated from business logic tests.
- Use `hypothesis` where properties matter: invariants, idempotency, schema evolution.
- Test names describe behavior.
- No shared mutable state.

## Commands

```bash
uv run pytest tests/ -v
uv run pytest tests/application/ -v
uv run pytest tests/api/ -v
make runtime-conformance
uv run pytest tests/ --cov=packages --cov-report=term-missing
```
