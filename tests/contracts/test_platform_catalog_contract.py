from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ._helpers import ROOT, load_json


CATALOG_ROOT = ROOT / "infra" / "catalog"
EXAMPLES_ROOT = ROOT / "examples"

CATALOG_MANIFEST_KEYS = {
    "schema_version",
    "runtime_target",
    "owner",
    "description",
    "entries",
}

CATALOG_ENTRY_KEYS = {
    "id",
    "type",
    "provides",
    "consumes_contract",
    "implementation",
    "adoption_steps",
}

CATALOG_FORBIDDEN_KEYS = {
    "admitted",
    "app_code",
    "app_path",
    "chart",
    "command",
    "crd",
    "deployment",
    "deployment_steps",
    "deploy",
    "env",
    "files",
    "generates",
    "helm",
    "image",
    "kustomization",
    "ports",
    "resource_name",
    "resources",
    "runtime_resources",
    "scaffold",
    "secrets",
    "service_name",
    "supported",
    "task_definition",
    "templates",
    "terraform",
    "workload",
    "workload_name",
    "workloads",
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


def _walk_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        keys: list[str] = []
        for key, nested in value.items():
            keys.append(str(key))
            keys.extend(_walk_keys(nested))
        return keys
    if isinstance(value, list):
        keys = []
        for item in value:
            keys.extend(_walk_keys(item))
        return keys
    return []


def test_catalog_manifests_describe_reusable_runtime_building_blocks() -> None:
    runtime_defaults = load_json("platform/runtime-defaults.json")
    runtime_targets = set(runtime_defaults["runtime_targets"])

    assert runtime_defaults["current_runtime_target"] == "aws-ecs"
    assert runtime_targets == {"local-compose", "local-kubernetes", "aws-ecs"}

    for path, manifest in _catalog_manifests():
        assert set(manifest) == CATALOG_MANIFEST_KEYS, path
        assert manifest["schema_version"] == "1"
        assert manifest["runtime_target"] in runtime_targets
        assert manifest["owner"]
        assert isinstance(manifest["entries"], list)
        assert manifest["entries"]
        forbidden_keys = sorted(
            {key for key in _walk_keys(manifest) if key in CATALOG_FORBIDDEN_KEYS}
        )
        assert forbidden_keys == [], (
            f"{path.relative_to(ROOT)} contains catalog keys that would make it "
            f"a second workload contract or deployment framework: {forbidden_keys}"
        )

        entry_ids: set[str] = set()
        for entry in manifest["entries"]:
            assert set(entry) == CATALOG_ENTRY_KEYS, path
            assert entry["id"] not in entry_ids
            entry_ids.add(entry["id"])
            assert entry["type"]
            for list_field in [
                "provides",
                "consumes_contract",
                "implementation",
                "adoption_steps",
            ]:
                assert isinstance(entry[list_field], list), (path, entry["id"])
                assert entry[list_field], (path, entry["id"], list_field)
                assert all(isinstance(item, str) for item in entry[list_field]), (
                    path,
                    entry["id"],
                    list_field,
                )


def test_examples_consume_platform_patterns_and_catalog_entries() -> None:
    workload_patterns = {
        pattern["name"]
        for pattern in load_json("platform/workload-patterns.json")["patterns"]
    }
    runtime_targets = set(
        load_json("platform/runtime-defaults.json")["runtime_targets"]
    )
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
