from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.ci import validate_platform_contract as validator


def _contract_copy() -> dict[str, Any]:
    return json.loads(validator.DEFAULT_CONTRACT.read_text(encoding="utf-8"))


def _write_contract(path: Path, contract: dict[str, Any]) -> None:
    path.write_text(json.dumps(contract), encoding="utf-8")


def _load_release_event_fields_via_importlib() -> list[tuple[str, ...]]:
    release_event_path = (
        validator.ROOT / "scripts" / "observability" / "release_event.py"
    )
    spec = importlib.util.spec_from_file_location(
        "release_event_importlib", release_event_path
    )
    assert spec is not None and spec.loader is not None, (
        f"spec_from_file_location returned None for {release_event_path}"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.REQUIRED_EVENT_FIELDS


def test_platform_contract_validator_accepts_current_workloads() -> None:
    assert validator.collect_errors() == []


def test_platform_contract_validator_rejects_missing_service_endpoint(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    ignore = shutil.ignore_patterns(".venv", ".git", ".pytest_cache", "__pycache__")
    shutil.copytree(validator.ROOT, root, ignore=ignore)

    api_main = root / "apps" / "api" / "main.py"
    api_main.write_text(
        api_main.read_text(encoding="utf-8").replace(
            '@app.get("/ready"', '# @app.get("/ready"', 1
        ),
        encoding="utf-8",
    )

    errors = validator.collect_errors(
        root=root,
        contract_path=root / "platform" / "workloads.json",
    )

    assert "api: missing FastAPI GET endpoint /ready" in errors


def test_platform_contract_validator_rejects_release_evidence_drift(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = _contract_copy()
    contract["release_evidence"]["required_fields"].remove("source_workflow")
    _write_contract(contract_path, contract)

    errors = validator.collect_errors(contract_path=contract_path)

    assert any("release_evidence.required_fields" in error for error in errors)


def test_platform_contract_validator_rejects_secret_env_overlap(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = _contract_copy()
    contract["workloads"][0]["config"]["env"].append("DB_PASSWORD")
    _write_contract(contract_path, contract)

    errors = validator.collect_errors(contract_path=contract_path)

    assert any(
        "secret names must not also appear in config.env" in error for error in errors
    )


def test_platform_contract_validator_rejects_missing_image_repository(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = _contract_copy()
    del contract["workloads"][0]["image"]["repository"]
    _write_contract(contract_path, contract)

    errors = validator.collect_errors(contract_path=contract_path)

    assert "api: image.repository must be a lowercase image repository name" in errors


def test_platform_contract_validator_rejects_database_config_drift(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = _contract_copy()
    contract["workloads"][0]["config"]["env"].remove("DB_HOST")
    contract["workloads"][0]["config"]["secrets"].remove("DB_PASSWORD")
    _write_contract(contract_path, contract)

    errors = validator.collect_errors(contract_path=contract_path)

    assert "api: database config.env is missing ['DB_HOST']" in errors
    assert "api: database config.secrets must include DB_PASSWORD" in errors


def test_platform_contract_validator_requires_trace_contract_for_jobs(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = _contract_copy()
    del contract["workloads"][2]["traces"]
    _write_contract(contract_path, contract)

    errors = validator.collect_errors(contract_path=contract_path)

    assert (
        "backfill_worker: traces.supported must be declared for every workload"
        in errors
    )


def test_platform_contract_validator_rejects_missing_conformance_env(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = _contract_copy()
    del contract["workloads"][0]["conformance"]["env"]["DATABASE_URL"]
    _write_contract(contract_path, contract)

    errors = validator.collect_errors(contract_path=contract_path)

    assert any(
        "conformance.env must match config.env exactly" in error for error in errors
    )


def test_platform_contract_validator_rejects_provider_named_workload_config(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = _contract_copy()
    contract["workloads"][0]["config"]["env"].append("AWS_REGION")
    contract["workloads"][0]["conformance"]["env"]["AWS_REGION"] = "eu-central-1"
    _write_contract(contract_path, contract)

    errors = validator.collect_errors(contract_path=contract_path)

    assert "api: config name AWS_REGION must stay provider-neutral" in errors


def test_check_release_evidence_no_errors_for_valid_contract() -> None:
    required_fields = [
        ".".join(path) for path in _load_release_event_fields_via_importlib()
    ]

    contract = {
        "release_evidence": {
            "required_fields": required_fields,
        }
    }
    errors: list[str] = []
    validator._check_release_evidence(contract, errors)

    assert errors == []


def test_check_release_evidence_raises_import_error_for_missing_file() -> None:
    contract = {
        "release_evidence": {
            "required_fields": [],
        }
    }
    errors: list[str] = []

    with patch("importlib.util.spec_from_file_location", return_value=None):
        try:
            validator._check_release_evidence(contract, errors)
        except ImportError as exc:
            assert "release_event.py" in str(exc) or "Cannot locate" in str(exc)
        else:
            raise AssertionError("Expected ImportError was not raised")


def test_importlib_and_direct_import_yield_same_required_event_fields() -> None:
    fields_via_importlib = _load_release_event_fields_via_importlib()

    repo_root = str(validator.ROOT)
    inserted = False
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
        inserted = True
    try:
        # Remove any cached version so we get a fresh load
        module_key = "scripts.observability.release_event"
        was_cached = module_key in sys.modules
        cached_module = sys.modules.pop(module_key, None)
        try:
            import scripts.observability.release_event as release_event_direct  # noqa: PLC0415

            fields_via_direct = release_event_direct.REQUIRED_EVENT_FIELDS
        finally:
            # Restore the module cache to its original state
            if was_cached and cached_module is not None:
                sys.modules[module_key] = cached_module
            elif not was_cached:
                sys.modules.pop(module_key, None)
    finally:
        if inserted:
            sys.path.remove(repo_root)

    assert fields_via_importlib == fields_via_direct
