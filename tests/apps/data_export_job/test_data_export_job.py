"""
Tests for data_export_job.main.run_export().

Validates: Requirements 5.1, 5.2
"""

from __future__ import annotations

import csv
import importlib
import json
import os
from urllib.parse import urlparse, urlunparse

from sqlalchemy import text

_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:6432/aws_sdlc_containers"
)
_parsed_database_url = urlparse(_TEST_DATABASE_URL)
_database_host = _parsed_database_url.hostname or "localhost"
if _database_host in {"db", "pgbouncer"}:
    _database_host = "localhost"
_database_auth = (
    f"{_parsed_database_url.username}:{_parsed_database_url.password}@"
    if _parsed_database_url.username
    else ""
)
os.environ.setdefault("DATABASE_URL", _TEST_DATABASE_URL)
os.environ.setdefault(
    "DATA_EXPORT_DATABASE_URL",
    urlunparse(
        _parsed_database_url._replace(netloc=f"{_database_auth}{_database_host}:5432")
    ),
)


def _load_data_export_job():
    settings = importlib.import_module("data_export_job.config").settings
    run_export = importlib.import_module("data_export_job.main").run_export
    return settings, run_export


def test_run_export_happy_path(committed_db_session, tmp_path, monkeypatch):
    """
    Validates: Requirements 5.1

    WHEN run_export() is called with a valid database URL and no S3 bucket,
    THE data_export_job SHALL write a CSV and JSON manifest to the output
    directory and return a manifest with status="succeeded".
    """
    settings, run_export = _load_data_export_job()
    monkeypatch.setattr(settings, "data_export_output_dir", str(tmp_path))
    monkeypatch.setattr(
        settings, "data_export_database_url", os.environ["DATABASE_URL"]
    )
    monkeypatch.setattr(settings, "data_export_s3_bucket", None)

    manifest = run_export()

    assert manifest["status"] == "succeeded"

    # CSV file must exist under tmp_path
    raw_key: str = manifest["objects"]["raw"]
    csv_path = tmp_path / raw_key
    assert csv_path.exists(), f"CSV not found at {csv_path}"

    # Manifest JSON file must exist under tmp_path
    manifest_key: str = manifest["objects"]["manifest"]
    manifest_path = tmp_path / manifest_key
    assert manifest_path.exists(), f"Manifest not found at {manifest_path}"

    # Manifest on disk must match the returned dict
    with manifest_path.open() as fh:
        on_disk = json.load(fh)
    assert on_disk["status"] == "succeeded"
    assert on_disk["row_count"] == manifest["row_count"]


def test_run_export_empty_table(committed_db_session, tmp_path, monkeypatch):
    """
    Validates: Requirements 5.2

    WHEN run_export() is called against a database with no rows in
    order_contact_email, THE data_export_job SHALL produce a CSV with only
    the header row and a manifest with row_count=0.
    """
    # Snapshot existing rows so we can restore them after the test.
    existing_rows = committed_db_session.execute(
        text(
            "SELECT order_id, billing_email, source, updated_at FROM order_contact_email"
        )
    ).fetchall()

    # Temporarily clear the table so the export sees an empty dataset.
    committed_db_session.execute(text("DELETE FROM order_contact_email"))
    committed_db_session.commit()

    try:
        settings, run_export = _load_data_export_job()
        monkeypatch.setattr(settings, "data_export_output_dir", str(tmp_path))
        monkeypatch.setattr(
            settings, "data_export_database_url", os.environ["DATABASE_URL"]
        )
        monkeypatch.setattr(settings, "data_export_s3_bucket", None)

        manifest = run_export()

        assert manifest["status"] == "succeeded"
        assert manifest["row_count"] == 0

        # CSV must exist and contain only the header row (no data rows)
        raw_key: str = manifest["objects"]["raw"]
        csv_path = tmp_path / raw_key
        assert csv_path.exists(), f"CSV not found at {csv_path}"

        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            rows = list(reader)

        # rows[0] is the header; there should be no further rows
        assert len(rows) == 1, f"Expected header-only CSV, got {len(rows)} rows"
        assert rows[0] == ["order_id", "billing_email", "source", "updated_at"]
    finally:
        # Restore the original rows.
        if existing_rows:
            committed_db_session.execute(
                text(
                    "INSERT INTO order_contact_email "
                    "(order_id, billing_email, source, updated_at) "
                    "VALUES (:order_id, :billing_email, :source, :updated_at) "
                    "ON CONFLICT (order_id) DO NOTHING"
                ),
                [
                    {
                        "order_id": r.order_id,
                        "billing_email": r.billing_email,
                        "source": r.source,
                        "updated_at": r.updated_at,
                    }
                    for r in existing_rows
                ],
            )
            committed_db_session.commit()
