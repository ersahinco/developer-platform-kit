# Requirements Document

## Introduction

The test suite has solid coverage across HTTP integration, application logic, consumer callbacks, data jobs, architecture contracts, scripts, and runtime conformance. This fills the remaining targeted gaps: write-mode branching in the order repository, the idempotency repository lifecycle, app-level wiring for two worker apps, and API-layer idempotency/admin edge cases.

## Glossary

- **Write Mode**: The `WRITE_MODE` runtime config value (`legacy`, `dual`, or `new`) controlling which tables `SQLAlchemyOrderRepository.create_order` writes to.
- **Committed DB Session**: A pytest fixture (`committed_db_session`) that commits data so subprocesses can see it, and cleans up afterwards.
- **TestClient**: FastAPI's `TestClient` used with `app.dependency_overrides` to test HTTP behaviour without a running server.

---

## Requirements

### Requirement 1 — Infrastructure: Order Repository Write Modes

**User Story:** As a developer, I want direct tests for `SQLAlchemyOrderRepository.create_order`, so that the three write-mode branches are verified at the repository level.

#### Acceptance Criteria

1. WHEN `create_order` is called with `WRITE_MODE=legacy`, THE `SQLAlchemyOrderRepository` SHALL persist `billing_email` to `orders.billing_email` and leave `order_contact_email` empty for that order.
2. WHEN `create_order` is called with `WRITE_MODE=dual`, THE `SQLAlchemyOrderRepository` SHALL persist `billing_email` to both `orders.billing_email` and `order_contact_email`.
3. WHEN `create_order` is called with `WRITE_MODE=new`, THE `SQLAlchemyOrderRepository` SHALL persist `billing_email` only to `order_contact_email` and store `NULL` in `orders.billing_email`.
4. WHEN `create_order` is called with `billing_email=None` and `WRITE_MODE=dual`, THE `SQLAlchemyOrderRepository` SHALL write no row to `order_contact_email` for that order.

### Requirement 2 — Infrastructure: Idempotency Repository

**User Story:** As a developer, I want direct tests for `SQLAlchemyIdempotencyRepository`, so that the begin/complete/fail lifecycle and conflict detection are verified at the repository level.

#### Acceptance Criteria

1. WHEN `begin` is called with a new key, THE `SQLAlchemyIdempotencyRepository` SHALL return `status="started"` and insert a row with `status="processing"`.
2. WHEN `begin` is called again with the same key and same hash while still processing, THE `SQLAlchemyIdempotencyRepository` SHALL return `status="processing"`.
3. WHEN `begin` is called after `complete`, THE `SQLAlchemyIdempotencyRepository` SHALL return `status="replay"` with the stored `response_status_code` and `response_payload`.
4. WHEN `begin` is called with an existing key but a different `request_hash`, THE `SQLAlchemyIdempotencyRepository` SHALL return `status="conflict"`.
5. WHEN `complete` is called, THE `SQLAlchemyIdempotencyRepository` SHALL update the row to `status="completed"` with the supplied payload.
6. WHEN `fail` is called, THE `SQLAlchemyIdempotencyRepository` SHALL update the row to `status="failed"` and store the truncated error.
7. WHEN `begin` is called with an expired `processing_expires_at`, THE `SQLAlchemyIdempotencyRepository` SHALL reset the row and return `status="started"`.

### Requirement 3 — Shared Fixture Helper

**User Story:** As a developer, I want a `make_customer` helper so that infrastructure tests can seed a customer row without duplicating raw SQL.

#### Acceptance Criteria

1. THE `Test Suite` SHALL provide `make_customer(session, *, name="Test Customer") -> int` in `tests/fixtures/factories.py` that inserts a `customers` row and returns its `id`.
2. THE `Test Suite` SHALL re-export `make_customer` from `tests/fixtures/__init__.py`.

### Requirement 4 — App-Level Tests: backfill_worker

**User Story:** As a developer, I want app-level tests for `backfill_worker`, so that subprocess wiring and the batch-cap control path are verified end-to-end.

#### Acceptance Criteria

1. WHEN invoked as a subprocess with a valid `BACKFILL_DATABASE_URL`, THE `backfill_worker` SHALL exit `0` and emit at least one JSON log line to stdout.
2. WHEN invoked with `BACKFILL_MAX_BATCHES=1` and `BACKFILL_BATCH_SIZE=1`, THE `backfill_worker` SHALL emit a `backfill_paused` or `backfill_complete` event and exit `0`.

### Requirement 5 — App-Level Tests: data_export_job

**User Story:** As a developer, I want app-level tests for `data_export_job`, so that `run_export()` wiring and the zero-row edge case are verified end-to-end.

#### Acceptance Criteria

1. WHEN `run_export()` is called with a valid database URL and no S3 bucket, THE `data_export_job` SHALL write a CSV and JSON manifest to the output directory and return a manifest with `status="succeeded"`.
2. WHEN `run_export()` is called against a database with no rows in `order_contact_email`, THE `data_export_job` SHALL produce a CSV with only the header row and a manifest with `row_count=0`.

### Requirement 6 — API: Idempotency Edge Cases

**User Story:** As a developer, I want the API idempotency edge cases covered, so that key-length validation and the still-processing conflict are verified.

#### Acceptance Criteria

1. WHEN `POST /orders` is called with an `Idempotency-Key` that is empty after stripping whitespace, THE `API` SHALL return HTTP 400.
2. WHEN `POST /orders` is called with an `Idempotency-Key` longer than 200 characters, THE `API` SHALL return HTTP 400.
3. WHEN `POST /orders` is called with an `Idempotency-Key` whose row is still processing, THE `API` SHALL return HTTP 409 with a "still processing" detail.

### Requirement 7 — API: Admin Endpoint Write Paths

**User Story:** As a developer, I want the admin endpoint write paths covered, so that valid mode values are persisted via the config store.

#### Acceptance Criteria

1. WHEN `POST /admin/write-mode` is called with a valid mode, THE `API` SHALL call `ConfigStore.set("WRITE_MODE", mode)` and return HTTP 200 with the accepted mode.
2. WHEN `POST /admin/read-mode` is called with a valid mode, THE `API` SHALL call `ConfigStore.set("READ_MODE", mode)` and return HTTP 200 with the accepted mode.
