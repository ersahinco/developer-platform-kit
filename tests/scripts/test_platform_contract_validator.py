from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import hypothesis.strategies as st
from hypothesis import given, settings

from scripts.ci import validate_platform_contract as validator


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
    contract = json.loads(validator.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    contract["release_evidence"]["required_fields"].remove("source_workflow")
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = validator.collect_errors(contract_path=contract_path)

    assert any("release_evidence.required_fields" in error for error in errors)


def test_platform_contract_validator_rejects_secret_env_overlap(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = json.loads(validator.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    contract["workloads"][0]["config"]["env"].append("DB_PASSWORD")
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = validator.collect_errors(contract_path=contract_path)

    assert any(
        "secret names must not also appear in config.env" in error for error in errors
    )


def test_platform_contract_validator_rejects_missing_image_repository(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = json.loads(validator.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    del contract["workloads"][0]["image"]["repository"]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = validator.collect_errors(contract_path=contract_path)

    assert "api: image.repository must be a lowercase image repository name" in errors


def test_platform_contract_validator_rejects_database_config_drift(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = json.loads(validator.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    contract["workloads"][0]["config"]["env"].remove("DB_HOST")
    contract["workloads"][0]["config"]["secrets"].remove("DB_PASSWORD")
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = validator.collect_errors(contract_path=contract_path)

    assert "api: database config.env is missing ['DB_HOST']" in errors
    assert "api: database config.secrets must include DB_PASSWORD" in errors


def test_platform_contract_validator_requires_trace_contract_for_jobs(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = json.loads(validator.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    del contract["workloads"][2]["traces"]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = validator.collect_errors(contract_path=contract_path)

    assert (
        "backfill_worker: traces.supported must be declared for every workload"
        in errors
    )


def test_platform_contract_validator_rejects_missing_runtime_capability(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "runtime-capabilities.json"
    contract = json.loads(
        validator.DEFAULT_RUNTIME_CONTRACT.read_text(encoding="utf-8")
    )
    del contract["runtime_targets"][0]["capabilities"]["ingress"]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = validator.collect_errors(runtime_contract_path=contract_path)

    assert any(
        "aws-ecs: capabilities must match required_capabilities exactly" in error
        for error in errors
    )


def test_platform_contract_validator_rejects_unsupported_runtime_capability_fields(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "runtime-capabilities.json"
    contract = json.loads(
        validator.DEFAULT_RUNTIME_CONTRACT.read_text(encoding="utf-8")
    )
    contract["runtime_targets"][0]["capabilities"]["terraform_ownership"][
        "required_tokens"
    ] = ["future_runtime_without_ownership_boundary"]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = validator.collect_errors(runtime_contract_path=contract_path)

    assert (
        "aws-ecs: capability terraform_ownership has unsupported fields ['required_tokens']"
        in errors
    )


def test_platform_contract_validator_rejects_missing_conformance_env(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = json.loads(validator.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    del contract["workloads"][0]["conformance"]["env"]["DATABASE_URL"]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = validator.collect_errors(contract_path=contract_path)

    assert any(
        "conformance.env must match config.env exactly" in error for error in errors
    )


def test_platform_contract_validator_rejects_unowned_runtime_provides(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "runtime-capabilities.json"
    contract = json.loads(
        validator.DEFAULT_RUNTIME_CONTRACT.read_text(encoding="utf-8")
    )
    contract["runtime_targets"][0]["capabilities"]["identity"]["owned_by"] = []
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = validator.collect_errors(runtime_contract_path=contract_path)

    assert "aws-ecs: capability identity needs owned_by" in errors


def test_platform_contract_validator_rejects_provider_named_workload_config(
    tmp_path: Path,
) -> None:
    contract_path = tmp_path / "workloads.json"
    contract = json.loads(validator.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    contract["workloads"][0]["config"]["env"].append("AWS_REGION")
    contract["workloads"][0]["conformance"]["env"]["AWS_REGION"] = "eu-central-1"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = validator.collect_errors(contract_path=contract_path)

    assert "api: config name AWS_REGION must stay provider-neutral" in errors


def test_platform_contract_validator_allows_future_runtime_specific_roots(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    ignore = shutil.ignore_patterns(".venv", ".git", ".pytest_cache", "__pycache__")
    shutil.copytree(validator.ROOT, root, ignore=ignore)
    (root / "infra" / "example-platform").mkdir()
    (root / "infra" / "example-app").mkdir()

    contract_path = root / "platform" / "runtime-capabilities.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    future_target = json.loads(json.dumps(contract["runtime_targets"][0]))
    future_target["name"] = "example-runtime"
    future_target["status"] = "supported"
    future_target["provider"] = "example"
    future_target["terraform_roots"] = {
        "bootstrap": "infra/example-platform",
        "runtime": "infra/example-app",
    }
    contract["runtime_targets"].append(future_target)
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = validator.collect_errors(
        root=root,
        contract_path=root / "platform" / "workloads.json",
        runtime_contract_path=contract_path,
    )

    assert errors == []


# ---------------------------------------------------------------------------
# Task 5.2 — unit tests for _check_release_evidence (importlib import fix)
# ---------------------------------------------------------------------------


def test_check_release_evidence_no_errors_for_valid_contract() -> None:
    """_check_release_evidence returns no errors when required_fields matches REQUIRED_EVENT_FIELDS."""
    # Build the expected required_fields list from the actual release_event module
    # (same derivation used inside _check_release_evidence)
    import importlib.util

    _spec = importlib.util.spec_from_file_location(
        "release_event",
        validator.ROOT / "scripts" / "observability" / "release_event.py",
    )
    assert _spec is not None and _spec.loader is not None
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    required_fields = [".".join(path) for path in _mod.REQUIRED_EVENT_FIELDS]

    contract = {
        "release_evidence": {
            "required_fields": required_fields,
        }
    }
    errors: list[str] = []
    validator._check_release_evidence(contract, errors)

    assert errors == []


def test_check_release_evidence_raises_import_error_for_missing_file() -> None:
    """_check_release_evidence raises ImportError when spec_from_file_location returns None."""
    contract = {
        "release_evidence": {
            "required_fields": [],
        }
    }
    errors: list[str] = []

    # Patch spec_from_file_location to return None, simulating a missing/unresolvable file.
    # This exercises the explicit ImportError guard inside _check_release_evidence.
    with patch("importlib.util.spec_from_file_location", return_value=None):
        try:
            validator._check_release_evidence(contract, errors)
        except ImportError as exc:
            assert "release_event.py" in str(exc) or "Cannot locate" in str(exc)
        else:
            raise AssertionError("Expected ImportError was not raised")


@settings(max_examples=1)
@given(st.just(None))
def test_importlib_and_direct_import_yield_same_required_event_fields(_: None) -> None:
    """**Validates: Requirements 5.1**

    Property 4: Loading REQUIRED_EVENT_FIELDS via importlib.util.spec_from_file_location
    must produce a value equal to the one obtained by directly importing
    scripts.observability.release_event — the import mechanism must not alter the value.
    """
    # --- Load via importlib (the mechanism used by validate_platform_contract.py) ---
    release_event_path = (
        validator.ROOT / "scripts" / "observability" / "release_event.py"
    )
    _spec = importlib.util.spec_from_file_location(
        "release_event_importlib", release_event_path
    )
    assert _spec is not None and _spec.loader is not None, (
        f"spec_from_file_location returned None for {release_event_path}"
    )
    _mod_importlib = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod_importlib)  # type: ignore[union-attr]
    fields_via_importlib = _mod_importlib.REQUIRED_EVENT_FIELDS

    # --- Load via direct import (sys.path manipulation, test-only) ---
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

    # --- Assert equivalence ---
    assert fields_via_importlib == fields_via_direct, (
        f"importlib load produced {fields_via_importlib!r} "
        f"but direct import produced {fields_via_direct!r}"
    )
