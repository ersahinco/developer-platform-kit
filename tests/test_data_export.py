import csv
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from sqlalchemy import text

_EXPORT_SRC = os.path.join(
    os.path.dirname(__file__), "..", "apps", "data-export-job", "src"
)


def _direct_database_url(env: dict[str, str]) -> str:
    db_url = env.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:6432/aws_sdlc_containers",
    )
    parsed = urlparse(db_url)
    direct = parsed._replace(netloc=f"{parsed.username}:{parsed.password}@localhost:5432")
    return urlunparse(direct)


def _run_export(output_dir: Path, run_id: str, export_date: str):
    env = {**os.environ}
    env["DATA_EXPORT_DATABASE_URL"] = _direct_database_url(env)
    env["DATA_EXPORT_OUTPUT_DIR"] = str(output_dir)
    env["DATA_EXPORT_RUN_ID"] = run_id
    env["DATA_EXPORT_DATE"] = export_date
    return subprocess.run(
        [
            "uv",
            "run",
            "--package",
            "aws-sdlc-containers-data-export-job",
            "python",
            "-m",
            "aws_sdlc_data_export_job.main",
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
    raw_path = tmp_path / "raw" / "order_contact_email" / "dt=2026-04-29" / "test-run.csv"
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
    assert manifest["row_count"] >= 1

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
