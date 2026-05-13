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
