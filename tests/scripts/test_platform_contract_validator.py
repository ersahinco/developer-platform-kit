from __future__ import annotations

import json
import shutil
from pathlib import Path

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
    contract["release_evidence"]["required_fields"].remove("github.run_id")
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
