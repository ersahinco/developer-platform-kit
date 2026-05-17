# Implementation Plan: scripts-audit-cleanup

## Overview

Mechanical housekeeping across six independent work streams: remove tracked bytecode, verify `.gitignore`, delete a redundant operator script and update its Make target, remove empty `__init__.py` boilerplate, fix a broken package import in the platform contract validator, and extract an inline Python heredoc into a standalone testable helper. No new abstractions are introduced. All CI workflows, Make targets, and the platform contract validator must remain fully functional after every task.

## Tasks

- [x] 1. Remove tracked `__pycache__` directories and `.pyc` files from git
  - Run `git rm -r scripts/__pycache__ scripts/ci/__pycache__ scripts/observability/__pycache__ scripts/release/__pycache__` to untrack and delete all committed bytecode
  - Confirm the orphaned `.pyc` for the non-existent `run_observability_cloud_jobs.py` is included in the removal
  - After deletion, `git status` must show no tracked `__pycache__/` directories or `.pyc` files under `scripts/`
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Verify `.gitignore` bytecode exclusion patterns
  - Read `.gitignore` and assert that both `__pycache__/` and `*.py[cod]` entries are present
  - If either entry is missing, add it; if both are present, no edit is needed (current state: both already exist)
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 3. Remove `db_seed_tunnel.sh` and update the `db-seed` Make target
  - [x] 3.1 Delete `scripts/operator/db_seed_tunnel.sh` from the repository
    - Use `git rm scripts/operator/db_seed_tunnel.sh`
    - _Requirements: 3.1_

  - [x] 3.2 Update the `db-seed` Make target in `Makefile`
    - Replace the `@bash scripts/operator/db_seed_tunnel.sh ...` invocation with a direct `uv run python scripts/data/seed_data.py` call
    - Set `SEED_NUM_CUSTOMERS` and `SEED_NUM_ORDERS` as inline env vars on the command
    - Update the target comment to indicate `make db-tunnel` must be run first for remote DBs
    - Exact replacement (per design):
      ```makefile
      .PHONY: db-seed
      db-seed: ## Seed DB — run make db-tunnel first for remote DBs  (SEED_NUM_CUSTOMERS=1000, SEED_NUM_ORDERS=10000)
      	SEED_NUM_CUSTOMERS=$(SEED_NUM_CUSTOMERS) SEED_NUM_ORDERS=$(SEED_NUM_ORDERS) \
      		uv run python scripts/data/seed_data.py
      ```
    - _Requirements: 3.2, 3.3, 3.4_

- [x] 4. Remove all `__init__.py` boilerplate files from `scripts/`
  - Run `git rm scripts/__init__.py scripts/ci/__init__.py scripts/data/__init__.py scripts/observability/__init__.py scripts/operator/__init__.py scripts/release/__init__.py`
  - All six files are empty; removing them has no runtime effect on scripts invoked via `uv run python <path>`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [ ] 5. Fix the absolute package import in `validate_platform_contract.py`
  - [ ] 5.1 Replace the `from scripts.observability.release_event import REQUIRED_EVENT_FIELDS` import (line ~408) with an `importlib.util.spec_from_file_location` based loader
    - The replacement must be self-contained inside `_check_release_evidence`, matching the existing lazy-import pattern
    - Use `ROOT / "scripts" / "observability" / "release_event.py"` as the file path (ROOT is already defined at module level)
    - Raise `ImportError` with a descriptive message if `_spec` or `_spec.loader` is `None`
    - Exact replacement per design:
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
      ```
    - _Requirements: 5.1, 5.3_

  - [x] 5.2 Write a unit test verifying the import fix works end-to-end
    - Call `_check_release_evidence` with a valid contract dict and assert no errors are returned
    - Call `_check_release_evidence` with a patched path pointing to a non-existent file and assert `ImportError` is raised
    - _Requirements: 5.2, 5.3_

  - [x] 5.3 Write property test for import equivalence (Property 4)
    - **Property 4: Path-based import yields the same REQUIRED_EVENT_FIELDS as the module defines**
    - Load `REQUIRED_EVENT_FIELDS` via `importlib.util.spec_from_file_location` and compare it to the value obtained by directly importing `scripts.observability.release_event` (with `sys.path` manipulation in the test only)
    - Assert the two values are equal for any valid `release_event.py`
    - **Validates: Requirements 5.1**

- [x] 6. Checkpoint — verify import fix before heredoc extraction
  - Run `uv run python scripts/ci/validate_platform_contract.py` and confirm it exits 0 and prints `platform contract: ok`
  - Run `uv run ruff check scripts/ci/validate_platform_contract.py` and confirm no errors
  - Ask the user if any questions arise before proceeding.

- [x] 7. Extract inline Python heredoc into `ci_strip_empty_tags.py`
  - [x] 7.1 Create `scripts/ci/ci_strip_empty_tags.py` with the extracted logic
    - Add module docstring, `strip_empty_tags(path: Path) -> None` function, and `main() -> int` entry point
    - Accept the task-definition JSON file path as `sys.argv[1]`; print usage to stderr and return 1 if argument count is wrong
    - Strip `tags` key only when its value is `[]`; write back with 2-space indent and trailing newline
    - Full file content per design document
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 7.2 Replace the heredoc block in `ci_register_ecs_task_definition.sh`
    - Remove the `python3 - "$TASK_DEFINITION_PATH" <<'PY' ... PY` block (lines 7–17)
    - Insert `python3 scripts/ci/ci_strip_empty_tags.py "$TASK_DEFINITION_PATH"` in its place
    - All other lines in the script remain unchanged
    - _Requirements: 6.3, 6.4, 6.6_

  - [x] 7.3 Write unit tests for `strip_empty_tags`
    - Test: `tags: []` → key removed from output file
    - Test: `tags: [{"key": "env", "value": "prod"}]` → key preserved unchanged
    - Test: no `tags` key present → file written back unchanged
    - _Requirements: 6.2_

  - [x] 7.4 Write property test for idempotency (Property 1)
    - **Property 1: Empty-tags stripping is idempotent**
    - For any task-definition JSON object, calling `strip_empty_tags` once and twice must produce identical file contents
    - **Validates: Requirements 6.2**

  - [x] 7.5 Write property test for non-empty/absent tags preservation (Property 2)
    - **Property 2: Non-empty or absent tags are preserved**
    - For any task-definition JSON where `tags` is absent or holds a non-empty list, `strip_empty_tags` must leave the `tags` field unchanged
    - **Validates: Requirements 6.2**

  - [x] 7.6 Write property test for field preservation (Property 3)
    - **Property 3: Strip-then-parse round trip preserves all other fields**
    - For any task-definition JSON object, after `strip_empty_tags`, all fields other than `tags` must be present with identical values
    - **Validates: Requirements 6.2, 6.4**

- [ ] 8. Final checkpoint — full smoke checkDownloads/aws-sdlc-containers main +7 !10 ?3 ❯ uv run ruff check scripts/ci/ci_strip_empty_tags.py; echo "Exit code: $?"                                                                             21:49:49
All checks passed!
Exit code: 0
~/Downloads/aws-sdlc-containers main +7 !10 ?3 ❯                                                                                                                                                       21:49:50
~/Downloads/aws-sdlc-containers main +7 !10 ?3 ❯ bash -n scripts/ci/ci_register_ecs_task_definition.sh; echo "Exit code: $?"                                                                     ✘ INT 21:49:56
Exit code: 0
~/Downloads/aws-sdlc-containers main +7 !10 ?3 ❯    ∫
  - Run `bash -n scripts/ci/ci_register_ecs_task_definition.sh` and confirm exit 0
  - Run `uv run ruff check scripts/ci/ci_strip_empty_tags.py` and confirm no errors
  - Run `uv run python scripts/ci/validate_platform_contract.py` and confirm exit 0 with `platform contract: ok`
  - Confirm no `__pycache__/` directories, `.pyc` files, or `__init__.py` files remain under `scripts/`
  - Confirm `scripts/operator/db_seed_tunnel.sh` does not exist
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks 1, 2, 3, 4 are fully independent and can be executed in any order
- Task 5 (import fix) depends on Task 4 (`__init__.py` removal) — the import breaks only after `scripts/__init__.py` is deleted
- Task 7 (heredoc extraction) is independent of all other tasks
- Tasks marked with `*` are optional and can be skipped for a faster pass
- Each task references specific requirements for traceability
- Property tests use `hypothesis` (already in the project's dev dependencies)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1", "2", "3.1", "4", "7.1"] },
    { "id": 1, "tasks": ["3.2", "7.2"] },
    { "id": 2, "tasks": ["5.1"] },
    { "id": 3, "tasks": ["5.2", "5.3", "7.3", "7.4", "7.5", "7.6"] }
  ]
}
```
