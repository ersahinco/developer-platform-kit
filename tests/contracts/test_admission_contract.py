from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from scripts.platform.admission_check import validate_candidate


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "platform" / "admission" / "workload-candidate.schema.json"
SAMPLE_PATH = (
    ROOT
    / "platform"
    / "admission"
    / "candidates"
    / "bounded-dependency-entraid-dns.json"
)
CATALOG_PATH = ROOT / "infra" / "catalog" / "aws" / "bounded-dependencies.yaml"


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_admission_schema_is_valid_json_schema() -> None:
    schema = _load_json(SCHEMA_PATH)

    Draft202012Validator.check_schema(schema)


def test_admission_candidate_validates_against_schema() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/admission_check.py",
            "--candidate",
            str(SAMPLE_PATH),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert f"{SAMPLE_PATH}\tok" in completed.stdout


def test_admission_schema_enforces_service_shape() -> None:
    candidate = _load_json(SAMPLE_PATH)
    candidate["operational"]["class"] = "operator-job"
    schema = _load_json(SCHEMA_PATH)

    errors = list(Draft202012Validator(schema).iter_errors(candidate))

    assert any("edge-service" in error.message for error in errors)


def test_admission_schema_accepts_dapr_service_invocation_scope() -> None:
    candidate = _load_json(SAMPLE_PATH)
    candidate["dapr"] = {
        "app_id": "candidate-api",
        "scope": "service-invocation",
    }
    schema = _load_json(SCHEMA_PATH)

    assert list(Draft202012Validator(schema).iter_errors(candidate)) == []


def test_admission_schema_rejects_runtime_and_dependency_wiring() -> None:
    candidate = _load_json(SAMPLE_PATH)
    candidate["runtime"]["ecs_task_definition"] = "payments-task"
    candidate["bounded_dependencies"][0]["issuer_url"] = "https://id.example"
    validator = Draft202012Validator(_load_json(SCHEMA_PATH))

    messages = {error.message for error in validator.iter_errors(candidate)}

    assert any("ecs_task_definition" in message for message in messages)
    assert any("issuer_url" in message for message in messages)


def test_admission_rejects_undeclared_bounded_dependency_config(
    tmp_path: Path,
) -> None:
    candidate = _load_json(SAMPLE_PATH)
    candidate["config"]["env"].remove("PARTNER_DNS_ZONE")
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    validator = Draft202012Validator(_load_json(SCHEMA_PATH))

    errors = validate_candidate(candidate_path, validator)

    assert errors == [
        "semantic $.bounded_dependencies[1].config.env: not declared in "
        "$.config.env: PARTNER_DNS_ZONE"
    ]


def test_bounded_dependency_catalog_covers_admission_kinds() -> None:
    schema = _load_json(SCHEMA_PATH)
    kinds = set(
        schema["properties"]["bounded_dependencies"]["items"]["properties"]["kind"][
            "enum"
        ]
    )
    catalog = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    consumed = {
        item.removeprefix("bounded dependency kind ")
        for entry in catalog["entries"]
        for item in entry["consumes_contract"]
        if item.startswith("bounded dependency kind ")
    }

    assert consumed == kinds
