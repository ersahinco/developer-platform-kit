# Design Document

## Feature: scripts-audit-cleanup

## Overview

This is a housekeeping cleanup of the `scripts/` directory and related repository hygiene artifacts. The work is purely mechanical: delete stale files, update `.gitignore`, fix one broken import, update one Make target, and extract one inline Python heredoc into a standalone helper. No new abstractions are introduced. All existing CI workflows, Make targets, and the platform contract validator must remain fully functional after the changes.

The cleanup is organized into six independent work streams that can be executed in any order, with one dependency: Requirement 5 (fix the import in `validate_platform_contract.py`) must be completed after Requirement 4 (remove `__init__.py` files), since removing `scripts/__init__.py` is what breaks the existing absolute import.

---

## Architecture

No architectural changes. The repository structure after cleanup:

```
scripts/
├── ci/
│   ├── ci_assert_ecs_task_succeeded.sh
│   ├── ci_deploy_ecs_service.sh
│   ├── ci_guard_infra_plan_blast_radius.sh
│   ├── ci_poll_ecs_task_until_stopped.sh
│   ├── ci_prepare_liquibase_task_definition.py
│   ├── ci_register_ecs_task_definition.sh   ← heredoc removed, python3 call added
│   ├── ci_render_ecs_task_definition.sh
│   ├── ci_resolve_ecs_network.sh
│   ├── ci_run_ecs_task.sh
│   ├── ci_set_app_drill_fault.py
│   ├── ci_strip_empty_tags.py               ← NEW
│   └── validate_platform_contract.py        ← import fixed
├── data/
│   └── seed_data.py
├── observability/
│   ├── generate_cloud_traffic.py
│   ├── incident_evidence_bundle.py
│   ├── release_event.py
│   ├── verify_observability_delivery.py
│   └── verify_release_event_loki_delivery.py
├── operator/
│   ├── db_exec.sh
│   └── db_tunnel.sh                         ← db_seed_tunnel.sh removed
└── release/
    └── verify_post_deploy.py
```

Files deleted:
- `scripts/__init__.py`
- `scripts/ci/__init__.py`
- `scripts/data/__init__.py`
- `scripts/observability/__init__.py`
- `scripts/operator/__init__.py`
- `scripts/release/__init__.py`
- `scripts/operator/db_seed_tunnel.sh`
- `scripts/__pycache__/` (entire directory)
- `scripts/ci/__pycache__/` (entire directory)
- `scripts/observability/__pycache__/` (entire directory)
- `scripts/release/__pycache__/` (entire directory)

---

## Components and Interfaces

### 1. Stale Bytecode Removal (Requirement 1)

**What exists today:**

| Path | Issue |
|------|-------|
| `scripts/__pycache__/__init__.cpython-314.pyc` | Tracked bytecode |
| `scripts/ci/__pycache__/__init__.cpython-314.pyc` | Tracked bytecode |
| `scripts/ci/__pycache__/validate_platform_contract.cpython-314.pyc` | Tracked bytecode |
| `scripts/observability/__pycache__/__init__.cpython-314.pyc` | Tracked bytecode |
| `scripts/observability/__pycache__/generate_cloud_traffic.cpython-314.pyc` | Tracked bytecode |
| `scripts/observability/__pycache__/incident_evidence_bundle.cpython-314.pyc` | Tracked bytecode |
| `scripts/observability/__pycache__/release_event.cpython-314.pyc` | Tracked bytecode |
| `scripts/observability/__pycache__/run_observability_cloud_jobs.cpython-314.pyc` | Orphaned — no source file |
| `scripts/observability/__pycache__/verify_observability_delivery.cpython-314.pyc` | Tracked bytecode |
| `scripts/observability/__pycache__/verify_release_event_loki_delivery.cpython-314.pyc` | Tracked bytecode |
| `scripts/release/__pycache__/__init__.cpython-314.pyc` | Tracked bytecode |
| `scripts/release/__pycache__/verify_post_deploy.cpython-314.pyc` | Tracked bytecode |
| `scripts/release/__pycache__/verify_prometheus_rollout.cpython-314.pyc` | Tracked bytecode |

**Action:** `git rm -r scripts/__pycache__ scripts/ci/__pycache__ scripts/observability/__pycache__ scripts/release/__pycache__`

### 2. `.gitignore` Verification (Requirement 2)

The current `.gitignore` already contains both required patterns:

```
__pycache__/
*.py[cod]
```

`*.py[cod]` covers `.pyc`, `.pyo`, and `.pyd`. No edits are needed. The task is to verify these entries are present and document that they are already correct.

### 3. Redundant Script Removal (Requirement 3)

**`scripts/operator/db_seed_tunnel.sh`** is a 60-line script that:
1. Resolves Terraform outputs to find the ECS cluster, RDS host, and DB secret
2. Opens an SSM port-forward tunnel to RDS on `localhost:15433`
3. Runs `uv run python scripts/data/seed_data.py` with the tunnel's `DATABASE_URL`

The `make db-tunnel` target already handles step 2 (tunnel to `localhost:15432`). The `make db-seed` target currently delegates to `db_seed_tunnel.sh`, which duplicates the tunnel setup.

**Makefile change — `db-seed` target:**

Current:
```makefile
.PHONY: db-seed
db-seed: ## Seed DB via SSM tunnel  (SEED_NUM_CUSTOMERS=1000, SEED_NUM_ORDERS=10000)
	@bash scripts/operator/db_seed_tunnel.sh $(SEED_NUM_CUSTOMERS) $(SEED_NUM_ORDERS) $(AWS_REGION)
```

After:
```makefile
.PHONY: db-seed
db-seed: ## Seed DB — run make db-tunnel first for remote DBs  (SEED_NUM_CUSTOMERS=1000, SEED_NUM_ORDERS=10000)
	SEED_NUM_CUSTOMERS=$(SEED_NUM_CUSTOMERS) SEED_NUM_ORDERS=$(SEED_NUM_ORDERS) \
		uv run python scripts/data/seed_data.py
```

The comment on the target serves as the documentation required by Requirement 3.4. For remote seeding, the developer runs `make db-tunnel` in one terminal and `make db-seed` in another, setting `DATABASE_URL` to point at the tunnel port.

**Note:** `db_seed_tunnel.sh` also handled Terraform output resolution and secret retrieval for the `DATABASE_URL`. After removal, remote seeding requires the developer to set `DATABASE_URL` manually (or use `make db-tunnel` which sets up the port-forward, then export `DATABASE_URL` pointing to `localhost:15432`). This is the intended workflow documented in the Makefile comment.

### 4. `__init__.py` Removal (Requirement 4)

Six files deleted:
- `scripts/__init__.py`
- `scripts/ci/__init__.py`
- `scripts/data/__init__.py`
- `scripts/observability/__init__.py`
- `scripts/operator/__init__.py`
- `scripts/release/__init__.py`

None of these files contain any code — they are empty boilerplate. Removing them has no runtime effect on the scripts themselves, which are invoked directly via `python3 <path>` or `uv run python <path>`, not via package imports.

The one exception is `validate_platform_contract.py`, which uses `scripts` as a package namespace for its import of `release_event`. That import is fixed in Requirement 5.

### 5. Import Fix in `validate_platform_contract.py` (Requirement 5)

**Current code** (line ~408):
```python
def _check_release_evidence(contract: dict[str, Any], errors: list[str]) -> None:
    from scripts.observability.release_event import REQUIRED_EVENT_FIELDS
    ...
```

This import works today because `scripts/__init__.py` exists and `sys.path.insert(0, str(ROOT))` is called at module level (line ~75 of the file). After `scripts/__init__.py` is removed, `scripts` is no longer a package and this import will fail with `ModuleNotFoundError`.

**Fix — use `importlib` with an explicit file path:**

```python
def _check_release_evidence(contract: dict[str, Any], errors: list[str]) -> None:
    import importlib.util

    _spec = importlib.util.spec_from_file_location(
        "release_event",
        ROOT / "scripts" / "observability" / "release_event.py",
    )
    if _spec is None or _spec.loader is None:
        raise ImportError(
            "Cannot locate scripts/observability/release_event.py — "
            "ensure the file exists relative to the repository root."
        )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    REQUIRED_EVENT_FIELDS = _mod.REQUIRED_EVENT_FIELDS
    ...
```

This approach:
- Does not require `scripts` to be a package
- Does not add `scripts/observability` to `sys.path` (avoids polluting the module namespace)
- Raises `ImportError` with a descriptive message if the file is missing (satisfies Requirement 5.3)
- Is self-contained within `_check_release_evidence`, matching the existing lazy-import pattern

**Alternative considered:** Adding `scripts/observability` to `sys.path` and doing `from release_event import REQUIRED_EVENT_FIELDS`. Rejected because it pollutes `sys.path` with a non-package directory and could shadow other modules named `release_event`.

### 6. Heredoc Extraction (Requirement 6)

**Current inline heredoc in `ci_register_ecs_task_definition.sh`:**

```bash
python3 - "$TASK_DEFINITION_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
task_definition = json.loads(path.read_text(encoding="utf-8"))

if task_definition.get("tags") == []:
    del task_definition["tags"]

path.write_text(json.dumps(task_definition, indent=2) + "\n", encoding="utf-8")
PY
```

**New file `scripts/ci/ci_strip_empty_tags.py`:**

```python
#!/usr/bin/env python3
"""Strip the 'tags' key from a task-definition JSON file when its value is an empty list.

Usage:
    python3 scripts/ci/ci_strip_empty_tags.py <task-definition-json-path>

The file is modified in place. If 'tags' is absent or non-empty, the file is
written back unchanged (normalised JSON with 2-space indent and trailing newline).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def strip_empty_tags(path: Path) -> None:
    task_definition = json.loads(path.read_text(encoding="utf-8"))
    if task_definition.get("tags") == []:
        del task_definition["tags"]
    path.write_text(json.dumps(task_definition, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print(
            f"usage: {sys.argv[0]} <task-definition-json-path>",
            file=sys.stderr,
        )
        return 1
    strip_empty_tags(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Updated call in `ci_register_ecs_task_definition.sh`** (replaces the heredoc block):

```bash
python3 scripts/ci/ci_strip_empty_tags.py "$TASK_DEFINITION_PATH"
```

The `strip_empty_tags` function is extracted as a named, importable function to enable unit and property testing without subprocess invocation.

---

## Data Models

No new data models. The only data structure involved is the ECS task-definition JSON object, which is an existing AWS-defined schema. The relevant field is:

```json
{
  "tags": []   // present with empty list → strip the key
}
```

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| `ci_strip_empty_tags.py` called with wrong number of args | Prints usage to stderr, exits 1 |
| `ci_strip_empty_tags.py` given a path that does not exist | `Path.read_text` raises `FileNotFoundError` — propagates naturally, exits non-zero |
| `ci_strip_empty_tags.py` given malformed JSON | `json.loads` raises `json.JSONDecodeError` — propagates naturally, exits non-zero |
| `validate_platform_contract.py` cannot find `release_event.py` | Raises `ImportError` with descriptive message identifying the missing file |
| `make db-seed` run without a tunnel when targeting remote DB | `seed_data.py` will fail to connect — same behavior as before, user must run `make db-tunnel` first |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Empty-tags stripping is idempotent

*For any* task-definition JSON object, calling `strip_empty_tags` once and calling it twice should produce identical file contents — applying the strip a second time changes nothing.

**Validates: Requirements 6.2**

### Property 2: Non-empty or absent tags are preserved

*For any* task-definition JSON object where the `tags` key is either absent or holds a non-empty list, calling `strip_empty_tags` should leave the `tags` field unchanged (i.e., the output JSON contains the same `tags` value as the input, or still has no `tags` key if it was absent).

**Validates: Requirements 6.2**

### Property 3: Strip-then-parse round trip preserves all other fields

*For any* task-definition JSON object, after calling `strip_empty_tags`, all fields other than `tags` should be present in the output with identical values — the helper must not mutate any field except `tags`.

**Validates: Requirements 6.2, 6.4**

### Property 4: Path-based import yields the same REQUIRED_EVENT_FIELDS as the module defines

*For any* valid `release_event.py` file, loading `REQUIRED_EVENT_FIELDS` via `importlib.util.spec_from_file_location` should produce a value equal to the `REQUIRED_EVENT_FIELDS` attribute accessible by directly importing the module — the import mechanism must not alter the value.

**Validates: Requirements 5.1**

---

## Testing Strategy

Most acceptance criteria in this feature are one-time file operations (deletions, edits) that are verified by smoke checks — read the file system or run a linter and assert the expected state. Two areas have logic worth property-testing:

**`ci_strip_empty_tags.py`** — pure function over JSON data. Properties 1–3 above cover it with generated task-definition objects of varying shapes (tags absent, tags empty list, tags non-empty list, extra fields present).

**`validate_platform_contract.py` import fix** — Property 4 verifies the `importlib`-based loader is equivalent to a direct import. This is a round-trip equivalence check.

**Unit tests** (example-based) cover:
- `strip_empty_tags` with `tags: []` → key removed
- `strip_empty_tags` with `tags: [{"key": "env", "value": "prod"}]` → key preserved
- `strip_empty_tags` with no `tags` key → file unchanged
- `validate_platform_contract._check_release_evidence` with a valid contract → no errors
- `validate_platform_contract._check_release_evidence` with a missing `release_event.py` → `ImportError` raised

**Smoke checks** (single execution):
- No `__pycache__` directories under `scripts/` after cleanup
- No `.pyc` files under `scripts/` after cleanup
- No `__init__.py` files under `scripts/` after cleanup
- `scripts/operator/db_seed_tunnel.sh` does not exist
- `.gitignore` contains `__pycache__/` and `*.py[cod]`
- `bash -n scripts/ci/ci_register_ecs_task_definition.sh` exits 0
- `ruff check scripts/ci/ci_strip_empty_tags.py` exits 0
- `uv run python scripts/ci/validate_platform_contract.py` exits 0 and prints `platform contract: ok`
