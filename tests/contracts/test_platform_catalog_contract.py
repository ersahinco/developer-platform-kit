from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ._helpers import ROOT, load_json


CATALOG_ROOT = ROOT / "infra" / "catalog"

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

REALIZATION_MANIFEST_KEYS = {
    "schema_version",
    "kind",
    "description",
    "realizations",
}

REALIZATION_KEYS = {
    "id",
    "capability",
    "provider",
    "owner",
    "maturity",
    "lanes",
    "inputs",
    "secret_names",
    "outputs",
    "failure_modes",
    "evidence",
    "operational_limits",
    "implementation",
}

CAPABILITIES = {"compute", "database", "dns", "eventing", "storage"}
MATURITIES = {"reference", "reviewed-production"}
LANES = {"starter", "enterprise"}

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


def test_capability_realizations_are_explicit_and_operable() -> None:
    path = CATALOG_ROOT / "capability-realizations.yaml"
    manifest = _load_yaml(path)

    assert set(manifest) == REALIZATION_MANIFEST_KEYS
    assert manifest["schema_version"] == "1"
    assert manifest["kind"] == "capability-realizations"
    assert manifest["description"]

    ids: set[str] = set()
    capability_providers: set[tuple[str, str]] = set()
    for realization in manifest["realizations"]:
        assert set(realization) == REALIZATION_KEYS, realization.get("id")
        assert realization["id"] not in ids
        ids.add(realization["id"])
        assert realization["capability"] in CAPABILITIES
        assert realization["provider"]
        assert realization["owner"]
        assert realization["maturity"] in MATURITIES
        assert set(realization["lanes"]) <= LANES
        assert realization["lanes"]
        capability_providers.add((realization["capability"], realization["provider"]))
        for field in [
            "inputs",
            "secret_names",
            "outputs",
            "failure_modes",
            "evidence",
            "operational_limits",
            "implementation",
        ]:
            assert isinstance(realization[field], list), (realization["id"], field)
            if field != "secret_names":
                assert realization[field], (realization["id"], field)
            assert all(isinstance(item, str) for item in realization[field])
        for implementation in realization["implementation"]:
            assert (ROOT / implementation).exists(), (
                realization["id"],
                implementation,
            )

    assert {
        ("compute", "aws"),
        ("compute", "hetzner"),
        ("database", "aws"),
        ("database", "supabase"),
        ("dns", "aws"),
        ("dns", "cloudflare"),
        ("storage", "aws"),
    } <= capability_providers


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

    for path, manifest in _catalog_manifests():
        if manifest.get("kind") == "capability-realizations":
            continue
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
            for implementation in entry["implementation"]:
                assert (ROOT / implementation).exists(), (
                    path,
                    entry["id"],
                    implementation,
                )
