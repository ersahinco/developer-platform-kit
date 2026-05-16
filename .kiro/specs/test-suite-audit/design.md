# Design Document — test-suite-audit

## Overview

20 tests across 6 new files. No new frameworks or dependencies. All patterns copied directly from existing reference files.

---

## Test File Layout

```
tests/
├── fixtures/
│   ├── __init__.py       # re-exports make_customer
│   └── factories.py      # make_customer — single plain function
├── infrastructure/
│   ├── test_order_repository.py       # NEW — Req 1 (4 tests)
│   └── test_idempotency_repository.py # NEW — Req 2 (7 tests)
├── apps/
│   ├── backfill_worker/
│   │   └── test_backfill_worker_app.py  # NEW — Req 4 (2 tests)
│   └── data_export_job/
│       └── test_data_export_job.py      # NEW — Req 5 (2 tests)
└── api/
    └── test_api_idempotency_admin.py    # NEW — Req 6 + 7 (5 tests)
```

---

## Components

### `tests/fixtures/factories.py`

```python
from sqlalchemy.orm import Session
from sqlalchemy import text

def make_customer(session: Session, *, name: str = "Test Customer") -> int:
    row = session.execute(
        text("INSERT INTO customers (name, created_at) VALUES (:name, NOW()) RETURNING id"),
        {"name": name},
    ).fetchone()
    session.commit()
    return row.id
```

`tests/fixtures/__init__.py`:
```python
from tests.fixtures.factories import make_customer
__all__ = ["make_customer"]
```

### `tests/infrastructure/test_order_repository.py`

Reference: `test_order_outbox.py`. Seeds `app_runtime_config` via SQL, calls the repo, asserts DB state.

```python
def _set_modes(session, *, write: str, read: str) -> None:
    for key, val in [("WRITE_MODE", write), ("READ_MODE", read)]:
        session.execute(
            text("INSERT INTO app_runtime_config (key, value) VALUES (:k, :v) "
                 "ON CONFLICT (key) DO UPDATE SET value = :v"),
            {"k": key, "v": val},
        )
    session.commit()
    from infrastructure.db.repository import _read_mode_cache, _write_mode_cache
    _read_mode_cache.invalidate()
    _write_mode_cache.invalidate()
```

Each test reads the current modes before calling `_set_modes` and restores them in a `finally` block. Uses `committed_db_session` and `make_customer`.

4 tests: `WRITE_MODE=legacy`, `WRITE_MODE=dual`, `WRITE_MODE=new`, `billing_email=None` with `WRITE_MODE=dual`.

### `tests/infrastructure/test_idempotency_repository.py`

Reference: `test_order_outbox.py`. Uses `committed_db_session`. Each test generates a fresh `uuid.uuid4().hex` key.

7 tests covering: new key → `started`, same key still processing → `processing`, after complete → `replay`, different hash → `conflict`, `complete` persists payload, `fail` persists error, expired lock → `started`.

### `tests/apps/backfill_worker/test_backfill_worker_app.py`

Reference: `tests/data/test_backfill.py`. Same `subprocess.run` + `uv run --package` pattern. Same `BACKFILL_DATABASE_URL` derivation logic (rewrite `db`/`pgbouncer` host to `localhost:5432`). Uses `committed_db_session` to seed one order row.

2 tests: happy path (exit 0, JSON log line), bounded run (`BACKFILL_MAX_BATCHES=1 BACKFILL_BATCH_SIZE=1`, exit 0, `backfill_paused` or `backfill_complete` in stdout).

### `tests/apps/data_export_job/test_data_export_job.py`

Calls `run_export()` directly. Uses `tmp_path`. Patches `data_export_job.config.settings` attributes via `monkeypatch.setattr` (not env vars — pydantic-settings reads at import time):
- `settings.data_export_output_dir` → `str(tmp_path)`
- `settings.data_export_database_url` → `os.environ["DATABASE_URL"]` (the validator sets this; patch the resolved attribute, not the property)
- `settings.data_export_s3_bucket` → `None`

2 tests: happy path (CSV + manifest written, `status="succeeded"`), empty table (header-only CSV, `row_count=0`).

### `tests/api/test_api_idempotency_admin.py`

Reference: `test_api_operational.py`. Inline stubs, `_override_*` helpers, `TestClient`, `finally` cleanup.

```python
class _ProcessingIdempotencyRepo:
    def begin(self, *, key, request_hash):
        from application.idempotency import IdempotencyBeginResult
        return IdempotencyBeginResult(status="processing")
    def complete(self, *, key, response_status_code, response_payload): pass
    def fail(self, *, key, error): pass

class _RecordingConfigStore:
    def __init__(self): self.sets: list[tuple[str, str]] = []
    def get(self, key): return None
    def set(self, key, value): self.sets.append((key, value))
```

5 tests: empty key → 400, key >200 chars → 400, still-processing → 409, valid write-mode → 200 + config store called, valid read-mode → 200 + config store called.

---

## Notes

- `test_order_repository.py` must save/restore `WRITE_MODE`/`READ_MODE` and call `invalidate()` on both caches in `finally` blocks.
- `test_idempotency_repository.py` uses unique keys per test — no cleanup needed.
- `test_data_export_job.py` patches `settings` attributes directly, not env vars.
