from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from scripts.platform.workload_fit_check import BOUNDED_DEPENDENCY_DIRECTIONS
from scripts.platform.workload_fit_check import BOUNDED_DEPENDENCY_KINDS


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


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_admission_schema_is_valid_json_schema() -> None:
    schema = _load_json(SCHEMA_PATH)

    Draft202012Validator.check_schema(schema)


def test_bounded_dependency_schema_matches_fit_check_vocabulary() -> None:
    schema = _load_json(SCHEMA_PATH)
    dependency_item = schema["properties"]["bounded_dependencies"]["items"]

    assert (
        set(dependency_item["properties"]["kind"]["enum"]) == BOUNDED_DEPENDENCY_KINDS
    )
    assert (
        set(dependency_item["properties"]["direction"]["enum"])
        == BOUNDED_DEPENDENCY_DIRECTIONS
    )


def test_aws_catalog_covers_all_bounded_dependency_kinds() -> None:
    catalog = _load_yaml(CATALOG_PATH)
    text = "\n".join(
        "\n".join(entry["consumes_contract"]) for entry in catalog["entries"]
    )
    covered = set(re.findall(r"bounded dependency kind ([a-z-]+)", text))

    assert BOUNDED_DEPENDENCY_KINDS.issubset(covered)


def test_admission_sample_validates_schema_and_fit_check() -> None:
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
