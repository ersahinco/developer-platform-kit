import csv
import hashlib
import importlib
import json
import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import text

from tests.helpers.runtime_env import direct_postgres_url

_EXPORT_SRC = os.path.join(
    os.path.dirname(__file__), "..", "..", "apps", "data_export_job"
)


def _run_export(output_dir: Path, run_id: str, export_date: str):
    env = {**os.environ}
    env["DATABASE_URL"] = direct_postgres_url(env)
    env["DATA_EXPORT_OUTPUT_DIR"] = str(output_dir)
    env["DATA_EXPORT_RUN_ID"] = run_id
    env["DATA_EXPORT_DATE"] = export_date
    env.pop("DATA_EXPORT_S3_BUCKET", None)
    return subprocess.run(
        [
            "uv",
            "run",
            "--package",
            "aws-sdlc-containers-data-export-job",
            "python",
            "-m",
            "data_export_job.main",
        ],
        cwd=_EXPORT_SRC,
        env=env,
        capture_output=True,
        text=True,
    )


def _insert_contact_email(conn, billing_email: str) -> int:
    order_id = (
        conn.execute(
            text(
                "INSERT INTO orders (customer_id, total_amount, status, submitted_at, billing_email) "
                "VALUES (1, 10.00, 'SUBMITTED', NOW(), :email) RETURNING id"
            ),
            {"email": billing_email},
        )
        .fetchone()
        .id
    )
    conn.execute(
        text(
            "INSERT INTO order_contact_email (order_id, billing_email, source) "
            "VALUES (:order_id, :email, 'test') "
            "ON CONFLICT (order_id) DO UPDATE "
            "SET billing_email = :email, source = 'test', updated_at = NOW()"
        ),
        {"order_id": order_id, "email": billing_email},
    )
    return order_id


def test_data_export_writes_raw_csv_then_success_manifest(
    committed_db_session,
    tmp_path,
):
    conn = committed_db_session.connection()
    order_id = _insert_contact_email(conn, "export@example.com")
    conn.commit()

    result = _run_export(tmp_path, run_id="test-run", export_date="2026-04-29")

    assert result.returncode == 0, result.stderr
    event = json.loads(result.stdout)
    assert event["event"] == "data_export_succeeded"
    assert event["job_name"] == "order_contact_email_export"
    assert event["workload"] == "data_export_job"
    assert event["run_id"] == "test-run"
    assert event["status"] == "succeeded"
    assert "timestamp" in event
    raw_path = (
        tmp_path / "raw" / "order_contact_email" / "dt=2026-04-29" / "test-run.csv"
    )
    manifest_path = (
        tmp_path
        / "manifests"
        / "order_contact_email"
        / "dt=2026-04-29"
        / "test-run.json"
    )
    assert raw_path.exists()
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "succeeded"
    assert manifest["dataset"] == "order_contact_email"
    assert manifest["objects"]["raw"] == str(raw_path.relative_to(tmp_path))
    assert manifest["objects"]["manifest"] == str(manifest_path.relative_to(tmp_path))
    assert manifest["row_count"] >= 1
    assert manifest["raw_byte_count"] == raw_path.stat().st_size
    assert manifest["raw_sha256"] == hashlib.sha256(raw_path.read_bytes()).hexdigest()

    with raw_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    exported = {int(row["order_id"]): row["billing_email"] for row in rows}
    assert exported[order_id] == "export@example.com"


def test_data_export_is_idempotent_for_the_same_run_id(
    committed_db_session,
    tmp_path,
):
    conn = committed_db_session.connection()
    _insert_contact_email(conn, "idempotent-export@example.com")
    conn.commit()

    first = _run_export(tmp_path, run_id="same-run", export_date="2026-04-29")
    second = _run_export(tmp_path, run_id="same-run", export_date="2026-04-29")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr

    manifest_path = (
        tmp_path
        / "manifests"
        / "order_contact_email"
        / "dt=2026-04-29"
        / "same-run.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "same-run"
    assert manifest["objects"]["raw"].endswith("/same-run.csv")
    assert (
        manifest["raw_byte_count"]
        == (tmp_path / "raw" / "order_contact_email" / "dt=2026-04-29" / "same-run.csv")
        .stat()
        .st_size
    )


def _load_export_module(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/aws_sdlc_containers",
    )
    monkeypatch.syspath_prepend(_EXPORT_SRC)
    import infrastructure.data_export as export_main

    return importlib.reload(export_main)


class RecordingS3Client:
    def __init__(self, fail_on_key: str | None = None):
        self.fail_on_key = fail_on_key
        self.uploads: list[tuple[str, str]] = []

    def put_object(self, *, Bucket, Key, Body):
        self.uploads.append((Bucket, Key))
        if Key == self.fail_on_key:
            raise RuntimeError(f"failed upload: {Key}")
        Body.read()


def test_s3_publish_uploads_raw_before_manifest(monkeypatch, tmp_path):
    export_main = _load_export_module(monkeypatch)
    raw_path = tmp_path / "raw.csv"
    manifest_path = tmp_path / "manifest.json"
    raw_path.write_text(
        "order_id,billing_email\n1,export@example.com\n", encoding="utf-8"
    )
    manifest_path.write_text('{"status":"succeeded"}\n', encoding="utf-8")
    s3_client = RecordingS3Client()

    export_main.publish_s3_outputs(
        raw_path=raw_path,
        manifest_path=manifest_path,
        bucket="data-hub",
        raw_key="raw/order_contact_email/dt=2026-04-29/test-run.csv",
        manifest_key="manifests/order_contact_email/dt=2026-04-29/test-run.json",
        s3_client=s3_client,
    )

    assert s3_client.uploads == [
        ("data-hub", "raw/order_contact_email/dt=2026-04-29/test-run.csv"),
        (
            "data-hub",
            "manifests/order_contact_email/dt=2026-04-29/test-run.json",
        ),
    ]


def test_s3_publish_skips_manifest_when_raw_upload_fails(monkeypatch, tmp_path):
    export_main = _load_export_module(monkeypatch)
    raw_key = "raw/order_contact_email/dt=2026-04-29/test-run.csv"
    raw_path = tmp_path / "raw.csv"
    manifest_path = tmp_path / "manifest.json"
    raw_path.write_text(
        "order_id,billing_email\n1,export@example.com\n", encoding="utf-8"
    )
    manifest_path.write_text('{"status":"succeeded"}\n', encoding="utf-8")
    s3_client = RecordingS3Client(fail_on_key=raw_key)

    with pytest.raises(RuntimeError, match="failed upload"):
        export_main.publish_s3_outputs(
            raw_path=raw_path,
            manifest_path=manifest_path,
            bucket="data-hub",
            raw_key=raw_key,
            manifest_key="manifests/order_contact_email/dt=2026-04-29/test-run.json",
            s3_client=s3_client,
        )

    assert s3_client.uploads == [("data-hub", raw_key)]


def test_manifest_validation_rejects_raw_checksum_mismatch(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/aws_sdlc_containers",
    )
    from application.data_export import (
        ExportedObject,
        validate_success_manifest,
    )

    raw_path = tmp_path / "raw.csv"
    raw_path.write_text(
        "order_id,billing_email\n1,export@example.com\n", encoding="utf-8"
    )
    raw = ExportedObject(
        key="raw/order_contact_email/dt=2026-04-29/test-run.csv",
        byte_count=raw_path.stat().st_size,
        sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),
    )
    manifest = {
        "status": "succeeded",
        "row_count": 1,
        "raw_byte_count": raw_path.stat().st_size,
        "raw_sha256": hashlib.sha256(b"different raw content").hexdigest(),
        "objects": {
            "raw": "raw/order_contact_email/dt=2026-04-29/test-run.csv",
            "manifest": "manifests/order_contact_email/dt=2026-04-29/test-run.json",
        },
    }

    with pytest.raises(ValueError, match="raw_sha256 mismatch"):
        validate_success_manifest(raw=raw, manifest=manifest)
