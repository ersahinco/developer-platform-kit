# Implementation Plan: test-suite-audit

## Overview

20 tests across 6 new files. Each task creates exactly one file.

---

## Tasks

- [x] 1. Create fixture helper
  - [x] 1.1 Create `tests/fixtures/__init__.py`
    - `from tests.fixtures.factories import make_customer` + `__all__ = ["make_customer"]`
    - _Requirements: 3.2_

  - [x] 1.2 Create `tests/fixtures/factories.py`
    - `make_customer(session, *, name="Test Customer") -> int` — raw SQL INSERT into `customers`, commit, return `id`
    - _Requirements: 3.1_

- [x] 2. Implement infrastructure repository tests
  - [x] 2.1 Create `tests/infrastructure/test_order_repository.py`
    - `_set_modes(session, *, write, read)` helper: upserts both `app_runtime_config` rows, commits, calls `_read_mode_cache.invalidate()` / `_write_mode_cache.invalidate()`
    - Each test reads current modes before `_set_modes` and restores them in a `finally` block
    - Use `committed_db_session` and `make_customer` from `tests.fixtures`
    - Test `WRITE_MODE=legacy`: `billing_email` in `orders.billing_email`, no row in `order_contact_email`
    - Test `WRITE_MODE=dual`: `billing_email` in both tables
    - Test `WRITE_MODE=new`: `orders.billing_email` is NULL, row in `order_contact_email`
    - Test `billing_email=None` with `WRITE_MODE=dual`: no row in `order_contact_email`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 2.2 Create `tests/infrastructure/test_idempotency_repository.py`
    - Use `committed_db_session`; each test generates a fresh key via `uuid.uuid4().hex`
    - Test new key → `IdempotencyBeginResult(status="started")`, row has `status="processing"`
    - Test same key + same hash still processing → `status="processing"`
    - Test after `complete` → `status="replay"` with stored payload
    - Test same key + different hash → `status="conflict"`
    - Test `complete`: row updated to `status="completed"` with supplied payload
    - Test `fail`: row updated to `status="failed"` with truncated error
    - Test expired `processing_expires_at` → row reset, returns `status="started"`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 3. Implement app-level tests
  - [x] 3.1 Create `tests/apps/backfill_worker/test_backfill_worker_app.py`
    - Same `subprocess.run` + `uv run --package aws-sdlc-containers-backfill-worker python -m backfill_worker.main` pattern as `tests/data/test_backfill.py`
    - Same `BACKFILL_DATABASE_URL` derivation (rewrite `db`/`pgbouncer` host to `localhost:5432`)
    - Use `committed_db_session` to seed one order row for both tests
    - Test happy path: exit code `0`, at least one JSON log line in stdout
    - Test bounded run: `BACKFILL_MAX_BATCHES=1 BACKFILL_BATCH_SIZE=1`, exit code `0`, stdout contains `backfill_paused` or `backfill_complete`
    - _Requirements: 4.1, 4.2_

  - [x] 3.2 Create `tests/apps/data_export_job/test_data_export_job.py`
    - Call `run_export()` directly (import from `data_export_job.main`)
    - Patch via `monkeypatch.setattr`: `settings.data_export_output_dir` → `str(tmp_path)`, `settings.data_export_database_url` → `os.environ["DATABASE_URL"]`, `settings.data_export_s3_bucket` → `None`
    - Test happy path: CSV and manifest written to `tmp_path`, manifest `status="succeeded"`
    - Test empty table: assert `order_contact_email` is empty, CSV has only header row, manifest `row_count=0`
    - _Requirements: 5.1, 5.2_

- [x] 4. Implement API tests
  - [x] 4.1 Create `tests/api/test_api_idempotency_admin.py`
    - Follow `test_api_operational.py` exactly: inline stubs, `_override_*` helpers, `TestClient`, `finally` cleanup
    - `_ProcessingIdempotencyRepo`: `begin` always returns `IdempotencyBeginResult(status="processing")`; `complete`/`fail` are no-ops
    - `_RecordingConfigStore`: `get` returns `None`; `set` appends `(key, value)` to `self.sets`
    - Test empty `Idempotency-Key` (whitespace-only after strip) → HTTP 400
    - Test `Idempotency-Key` > 200 chars → HTTP 400
    - Test still-processing key → HTTP 409 with "still processing" detail
    - Test `POST /admin/write-mode` with `"dual"` → HTTP 200, `{"mode": "dual"}`, `config_store.sets == [("WRITE_MODE", "dual")]`
    - Test `POST /admin/read-mode` with `"new"` → HTTP 200, `{"mode": "new"}`, `config_store.sets == [("READ_MODE", "new")]`
    - _Requirements: 6.1, 6.2, 6.3, 7.1, 7.2_

---

## Notes

- Tasks 1.1 and 1.2 must exist before 2.1 which imports `make_customer`
- `test_order_repository.py` must save/restore modes and call `invalidate()` on both caches in `finally` blocks
- `test_data_export_job.py` patches `settings` attributes directly — not env vars

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["3.1", "3.2", "4.1"] }
  ]
}
```
