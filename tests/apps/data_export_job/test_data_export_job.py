"""
Tests for data_export_job.main.run_export().

Validates: Requirements 5.1, 5.2
"""

from __future__ import annotations

import csv
import json
import os

from sqlalchemy import text

from data_export_job.config import settings
from data_export_job.main import run_export


def test_run_export_happy_path(committed_db_session, tmp_path, monkeypatch):
    """
    Validates: Requirements 5.1

    WHEN run_export() is called with a valid database URL and no S3 bucket,
    THE data_export_job SHALL write a CSV and JSON manifest to the output
    directory and return a manifest with status="succeeded".
    """
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
    # Confirm the table is empty for this test (committed_db_session cleanup
    # removes rows inserted by other tests, but we assert here to be explicit).
    row_count = committed_db_session.execute(
        text("SELECT COUNT(*) FROM order_contact_email")
    ).scalar()
    assert row_count == 0, (
        f"order_contact_email is not empty ({row_count} rows); "
        "this test requires an empty table"
    )

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
