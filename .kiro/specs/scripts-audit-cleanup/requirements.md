# Requirements Document

## Introduction

This feature audits and cleans up the `scripts/` directory and related repository hygiene artifacts. The cleanup covers four categories: removal of dead/stale build artifacts, removal of redundant scripts superseded by existing Make targets, removal of unnecessary Python packaging boilerplate, and enforcement of best-practice gaps. One script (`scripts/ci/ci_register_ecs_task_definition.sh`) also has an embedded inline Python heredoc that must be extracted into a standalone helper. All changes must leave CI workflows, Make targets, and the platform contract validator fully functional.

## Glossary

- **Repository**: The `aws-sdlc-containers` git repository being cleaned up.
- **Cleanup Tool**: The set of manual file operations and code edits performed as part of this feature.
- **Stale Artifact**: A compiled Python bytecode file (`.pyc`) or `__pycache__/` directory committed to the Repository with no corresponding source file or that should never be tracked by git.
- **Redundant Script**: A shell script whose functionality is fully covered by an existing Make target or combination of existing scripts.
- **Boilerplate File**: An `__init__.py` file placed in a `scripts/` subdirectory solely to enable package-style imports, which are not required for standalone scripts.
- **Inline Heredoc**: A Python code block embedded directly inside a shell script using a `<<'PY'` heredoc construct.
- **Python Helper**: A standalone `.py` file that replaces an Inline Heredoc extracted from a shell script.
- **Platform Contract Validator**: `scripts/ci/validate_platform_contract.py`, which imports `scripts.observability.release_event` using an absolute package path.
- **gitignore**: The `.gitignore` file at the repository root that controls which files git tracks.

## Requirements

### Requirement 1 — Remove Stale Compiled Artifacts

**User Story:** As a developer, I want all committed `.pyc` files and `__pycache__/` directories removed from the Repository, so that the git history does not contain stale bytecode that can confuse tooling and reviewers.

#### Acceptance Criteria

1. THE Cleanup Tool SHALL delete `scripts/observability/__pycache__/run_observability_cloud_jobs.cpython-314.pyc` from the Repository, as no corresponding `run_observability_cloud_jobs.py` source file exists.
2. THE Cleanup Tool SHALL delete all `__pycache__/` directories and their contents that are currently tracked under `scripts/` in the Repository.
3. THE Cleanup Tool SHALL delete all `.pyc` files that are currently tracked under `scripts/` in the Repository.
4. WHEN a developer runs `git status` after the cleanup, THE Repository SHALL show no tracked `__pycache__/` directories or `.pyc` files under `scripts/`.

### Requirement 2 — Prevent Future Bytecode Commits

**User Story:** As a developer, I want `__pycache__/` directories and `*.pyc` files excluded by `.gitignore`, so that Python bytecode is never accidentally committed again.

#### Acceptance Criteria

1. THE Cleanup Tool SHALL verify that `.gitignore` already contains entries matching `__pycache__/` and `*.py[cod]` (or equivalent patterns covering `.pyc` files).
2. WHERE `.gitignore` does not already contain a `__pycache__/` entry, THE Cleanup Tool SHALL add `__pycache__/` to `.gitignore`.
3. WHERE `.gitignore` does not already contain a pattern covering `*.pyc` files, THE Cleanup Tool SHALL add `*.pyc` to `.gitignore`.
4. WHEN a developer stages a `.pyc` file or `__pycache__/` directory, THE Repository SHALL not include those paths in the commit.

### Requirement 3 — Remove Redundant Operator Script

**User Story:** As a developer, I want `scripts/operator/db_seed_tunnel.sh` removed, so that the codebase does not maintain a duplicate of functionality already available through `make db-tunnel` and `make db-seed`.

#### Acceptance Criteria

1. THE Cleanup Tool SHALL delete `scripts/operator/db_seed_tunnel.sh` from the Repository.
2. THE Cleanup Tool SHALL update the `db-seed` Make target in `Makefile` to invoke `scripts/data/seed_data.py` directly via `uv run python scripts/data/seed_data.py` rather than delegating to `db_seed_tunnel.sh`.
3. WHEN a developer runs `make db-seed`, THE Makefile SHALL execute `uv run python scripts/data/seed_data.py` with the `SEED_NUM_CUSTOMERS` and `SEED_NUM_ORDERS` environment variables set.
4. WHEN a developer needs to seed a remote database, THE Repository documentation or Makefile comments SHALL indicate that `make db-tunnel` followed by `make db-seed` achieves the same result as the removed script.

### Requirement 4 — Remove Unnecessary `__init__.py` Boilerplate

**User Story:** As a developer, I want all `__init__.py` files removed from `scripts/` and its subdirectories, so that the scripts directory is not treated as a Python package and does not carry unnecessary boilerplate.

#### Acceptance Criteria

1. THE Cleanup Tool SHALL delete `scripts/__init__.py` from the Repository.
2. THE Cleanup Tool SHALL delete `scripts/ci/__init__.py` from the Repository.
3. THE Cleanup Tool SHALL delete `scripts/data/__init__.py` from the Repository.
4. THE Cleanup Tool SHALL delete `scripts/observability/__init__.py` from the Repository.
5. THE Cleanup Tool SHALL delete `scripts/operator/__init__.py` from the Repository.
6. THE Cleanup Tool SHALL delete `scripts/release/__init__.py` from the Repository.
7. WHEN a developer lists the contents of any `scripts/` subdirectory, THE Repository SHALL contain no `__init__.py` files under `scripts/`.

### Requirement 5 — Fix Absolute Import in Platform Contract Validator

**User Story:** As a developer, I want `validate_platform_contract.py` updated to use a relative or path-based import for `release_event`, so that the script continues to work after `scripts/__init__.py` is removed.

#### Acceptance Criteria

1. THE Cleanup Tool SHALL replace the `from scripts.observability.release_event import REQUIRED_EVENT_FIELDS` absolute import in `scripts/ci/validate_platform_contract.py` with an import that does not rely on `scripts` being a Python package.
2. WHEN `uv run python scripts/ci/validate_platform_contract.py` is executed after the cleanup, THE Platform Contract Validator SHALL exit with code 0 and print `platform contract: ok` when the contract is valid.
3. IF the import resolution fails at runtime, THEN THE Platform Contract Validator SHALL raise an `ImportError` with a message identifying the missing module.

### Requirement 6 — Extract Inline Python Heredoc from CI Shell Script

**User Story:** As a developer, I want the inline Python heredoc in `scripts/ci/ci_register_ecs_task_definition.sh` extracted into a standalone Python helper, so that the Python logic is independently testable, lintable, and readable.

#### Acceptance Criteria

1. THE Cleanup Tool SHALL create a new file `scripts/ci/ci_strip_empty_tags.py` containing the Python logic currently embedded as a heredoc in `scripts/ci/ci_register_ecs_task_definition.sh`.
2. THE `ci_strip_empty_tags.py` helper SHALL accept a task-definition JSON file path as its first command-line argument and strip the `tags` key when its value is an empty list, writing the result back to the same file.
3. THE Cleanup Tool SHALL replace the inline heredoc block in `scripts/ci/ci_register_ecs_task_definition.sh` with a call to `python3 scripts/ci/ci_strip_empty_tags.py "$TASK_DEFINITION_PATH"`.
4. WHEN `scripts/ci/ci_register_ecs_task_definition.sh` is executed with a valid task-definition JSON file, THE script SHALL produce the same output and side effects as before the refactor.
5. WHEN `uv run ruff check scripts/ci/ci_strip_empty_tags.py` is executed, THE linter SHALL report no errors.
6. WHEN `bash -n scripts/ci/ci_register_ecs_task_definition.sh` is executed, THE shell syntax checker SHALL report no errors.
