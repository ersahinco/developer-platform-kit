from __future__ import annotations

import importlib
import json
from pathlib import Path

import duckdb


def _load_open_dataset_pipeline():
    settings = importlib.import_module("open_dataset_pipeline.config").settings
    run_pipeline = importlib.import_module("open_dataset_pipeline.main").run_pipeline
    return settings, run_pipeline


def _sample_dataset_url() -> str:
    dataset_path = (
        Path(__file__).resolve().parents[3]
        / "apps"
        / "open_dataset_pipeline"
        / "sample_data"
        / "iris.csv"
    )
    return dataset_path.as_uri()


def test_run_pipeline_materializes_raw_duckdb_and_manifest(tmp_path, monkeypatch):
    settings, run_pipeline = _load_open_dataset_pipeline()
    monkeypatch.setattr(settings, "open_dataset_url", _sample_dataset_url())
    monkeypatch.setattr(settings, "open_dataset_name", "iris")
    monkeypatch.setattr(settings, "open_dataset_output_dir", str(tmp_path))
    monkeypatch.setattr(settings, "open_dataset_run_id", "test-run")
    monkeypatch.setattr(settings, "open_dataset_date", "2026-05-21")

    manifest = run_pipeline()

    assert manifest["status"] == "succeeded"
    assert manifest["row_count"] == 4

    raw_path = tmp_path / manifest["objects"]["raw"]
    duckdb_path = tmp_path / manifest["objects"]["duckdb"]
    manifest_path = tmp_path / manifest["objects"]["manifest"]

    assert raw_path.is_file()
    assert duckdb_path.is_file()
    assert manifest_path.is_file()

    on_disk = json.loads(manifest_path.read_text())
    assert on_disk["status"] == "succeeded"
    assert on_disk["row_count"] == 4

    connection = duckdb.connect(str(duckdb_path))
    try:
        row = connection.execute(
            f"SELECT COUNT(*) FROM {manifest['table_name']}"
        ).fetchone()
        if row is None:
            raise RuntimeError("duckdb count query returned no rows")
        row_count = row[0]
    finally:
        connection.close()

    assert row_count == 4


def test_run_pipeline_is_repeatable_for_same_run_id(tmp_path, monkeypatch):
    settings, run_pipeline = _load_open_dataset_pipeline()
    monkeypatch.setattr(settings, "open_dataset_url", _sample_dataset_url())
    monkeypatch.setattr(settings, "open_dataset_name", "iris")
    monkeypatch.setattr(settings, "open_dataset_output_dir", str(tmp_path))
    monkeypatch.setattr(settings, "open_dataset_run_id", "repeatable-run")
    monkeypatch.setattr(settings, "open_dataset_date", "2026-05-21")

    first_manifest = run_pipeline()
    second_manifest = run_pipeline()

    assert first_manifest["objects"] == second_manifest["objects"]
    assert first_manifest["row_count"] == second_manifest["row_count"] == 4
