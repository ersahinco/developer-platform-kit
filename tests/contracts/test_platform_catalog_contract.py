from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ._helpers import ROOT, load_json


CATALOG_ROOT = ROOT / "infra" / "catalog"
EXAMPLES_ROOT = ROOT / "examples"

USE_CASE_SPECIFIC_TERMS = {
    "iris",
    "nyc",
    "taxi",
    "open_dataset",
    "open-dataset",
    "customer",
    "order",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _catalog_manifests() -> list[tuple[Path, dict[str, Any]]]:
    return [(path, _load_yaml(path)) for path in sorted(CATALOG_ROOT.glob("**/*.yaml"))]


def _example_manifests() -> list[tuple[Path, dict[str, Any]]]:
    return [
        (path, _load_yaml(path))
        for path in sorted(EXAMPLES_ROOT.glob("*/example.yaml"))
    ]


def _catalog_entry_refs() -> set[str]:
    refs: set[str] = set()
    for path, manifest in _catalog_manifests():
        rel_path = path.relative_to(ROOT).as_posix()
        for entry in manifest["entries"]:
            refs.add(f"{rel_path}#{entry['id']}")
    return refs


def test_catalog_manifests_describe_reusable_runtime_building_blocks() -> None:
    runtime_targets = {
        target["id"]
        for target in load_json("platform/platform-inventory.json")["runtime_targets"]
    }

    for path, manifest in _catalog_manifests():
        assert manifest["schema_version"] == "1"
        assert manifest["runtime_target"] in runtime_targets
        assert manifest["owner"]
        assert isinstance(manifest["entries"], list)
        assert manifest["entries"]

        entry_ids: set[str] = set()
        for entry in manifest["entries"]:
            assert entry["id"] not in entry_ids
            entry_ids.add(entry["id"])
            assert entry["type"]
            assert entry["provides"]
            assert entry["consumes_contract"]
            assert entry["implementation"]
            assert entry["adoption_steps"]

        text = path.read_text(encoding="utf-8").lower()
        for term in USE_CASE_SPECIFIC_TERMS:
            assert term not in text


def test_examples_consume_platform_patterns_and_catalog_entries() -> None:
    workload_patterns = {
        pattern["name"]
        for pattern in load_json("platform/workload-patterns.json")["patterns"]
    }
    runtime_targets = {
        target["id"]
        for target in load_json("platform/platform-inventory.json")["runtime_targets"]
    }
    catalog_refs = _catalog_entry_refs()

    for _path, manifest in _example_manifests():
        platform_usage = manifest["platform_usage"]
        assert set(platform_usage["workload_patterns"]).issubset(workload_patterns)
        assert set(platform_usage["runtime_targets"]).issubset(runtime_targets)
        assert set(platform_usage["catalog_entries"]).issubset(catalog_refs)
        assert platform_usage["proof"]["tests"]
        assert platform_usage["proof"]["commands"]


def test_examples_do_not_overlap_real_workloads() -> None:
    workload_names = {
        workload["name"]
        for workload in load_json("platform/workloads.json")["workloads"]
    }

    for _path, manifest in _example_manifests():
        assert manifest["name"] not in workload_names
