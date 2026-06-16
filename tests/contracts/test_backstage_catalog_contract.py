from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _load_yaml_documents(path: str) -> list[dict[str, Any]]:
    document_path = ROOT / path
    return [
        document
        for document in yaml.safe_load_all(document_path.read_text())
        if isinstance(document, dict)
    ]


def _load_catalog_entity_documents() -> list[dict[str, Any]]:
    return [
        yaml.safe_load(path.read_text())
        for path in sorted((ROOT / "catalog").glob("*.yaml"))
        if isinstance(yaml.safe_load(path.read_text()), dict)
    ]


def _load_workload_names() -> list[str]:
    workloads = json.loads((ROOT / "platform" / "workloads.json").read_text())[
        "workloads"
    ]
    return [
        workload["name"]
        for workload in workloads
        if isinstance(workload, dict) and isinstance(workload.get("name"), str)
    ]


def _load_workload_kinds() -> dict[str, str]:
    workloads = json.loads((ROOT / "platform" / "workloads.json").read_text())[
        "workloads"
    ]
    return {
        workload["name"]: workload["kind"]
        for workload in workloads
        if isinstance(workload, dict)
        and isinstance(workload.get("name"), str)
        and isinstance(workload.get("kind"), str)
    }


def _load_workload_use_cases() -> dict[str, list[str]]:
    workloads = json.loads((ROOT / "platform" / "workloads.json").read_text())[
        "workloads"
    ]
    return {
        workload["name"]: workload["use_cases"]
        for workload in workloads
        if isinstance(workload, dict)
        and isinstance(workload.get("name"), str)
        and isinstance(workload.get("use_cases"), list)
    }


def _load_workload_owners() -> dict[str, str]:
    workloads = json.loads((ROOT / "platform" / "workloads.json").read_text())[
        "workloads"
    ]
    return {
        workload["name"]: workload["owner"]
        for workload in workloads
        if isinstance(workload, dict)
        and isinstance(workload.get("name"), str)
        and isinstance(workload.get("owner"), str)
    }


def _load_workload_runtime_dependencies() -> dict[str, list[str]]:
    workloads = json.loads((ROOT / "platform" / "workloads.json").read_text())[
        "workloads"
    ]
    dependencies: dict[str, list[str]] = {}
    for workload in workloads:
        if not isinstance(workload, dict):
            continue
        name = workload.get("name")
        runtime = workload.get("runtime", {})
        if not isinstance(name, str) or not isinstance(runtime, dict):
            continue
        supported = [
            value for value in runtime.get("supported", []) if isinstance(value, str)
        ]
        admitted = [
            value for value in runtime.get("admitted", []) if isinstance(value, str)
        ]
        ordered = list(dict.fromkeys([*supported, *admitted]))
        dependencies[name] = [
            f"resource:default/runtime-target-{runtime_target}"
            for runtime_target in ordered
        ]
    return dependencies


def test_catalog_info_declares_backstage_location_for_platform_entities() -> None:
    documents = _load_yaml_documents("catalog-info.yaml")
    assert len(documents) == 1
    location = documents[0]
    targets = location["spec"]["targets"]

    assert location["kind"] == "Location"
    assert location["metadata"]["name"] == "aws-sdlc-containers-catalog"
    assert location["spec"]["type"] == "file"
    assert isinstance(targets, list)
    assert targets
    assert all((ROOT / target.removeprefix("./")).is_file() for target in targets)
    component_targets = {
        Path(target).name for target in targets if target.startswith("./catalog/")
    }
    catalog_files = {path.name for path in sorted((ROOT / "catalog").glob("*.yaml"))}
    assert component_targets == catalog_files


def test_catalog_entity_files_declare_backstage_entities_for_platform_and_workloads() -> (
    None
):
    documents = _load_catalog_entity_documents()
    entities = {
        (document.get("kind"), document.get("metadata", {}).get("name")): document
        for document in documents
    }

    assert ("Group", "platform-engineering") in entities
    assert ("Domain", "platform-engineering") in entities
    assert ("System", "aws-sdlc-containers") in entities
    assert ("Resource", "runtime-target-local-compose") in entities
    assert ("Resource", "runtime-target-local-kubernetes") in entities
    assert ("Resource", "runtime-target-aws-ecs") in entities
    assert ("Component", "platform-monorepo") in entities


def test_platform_catalog_exposes_generated_capability_profile_metadata() -> None:
    documents = _load_catalog_entity_documents()
    platform = next(
        document
        for document in documents
        if document.get("kind") == "Component"
        and document.get("metadata", {}).get("name") == "platform-monorepo"
    )
    annotations = platform["metadata"]["annotations"]

    assert (
        annotations["aws-sdlc-containers/capability-profile-command"]
        == "make monorepo-capability-profile"
    )
    assert (
        annotations["aws-sdlc-containers/capability-profile-artifact"]
        == "monorepo-capability-profile-${github.run_id}"
    )
    assert (
        annotations["aws-sdlc-containers/capability-profile-schema"]
        == "lean-monorepo-capabilities/v1"
    )


def test_catalog_info_workload_components_match_workload_contract() -> None:
    documents = _load_catalog_entity_documents()
    component_entities = {
        document["metadata"]["name"]: document
        for document in documents
        if document.get("kind") == "Component"
        and isinstance(document.get("metadata"), dict)
        and isinstance(document["metadata"].get("name"), str)
        and document["metadata"]["name"] != "platform-monorepo"
    }

    workload_names = _load_workload_names()
    workload_kinds = _load_workload_kinds()
    workload_owners = _load_workload_owners()
    workload_use_cases = _load_workload_use_cases()
    workload_runtime_dependencies = _load_workload_runtime_dependencies()

    assert sorted(component_entities) == sorted(workload_names)

    for workload_name in workload_names:
        component = component_entities[workload_name]
        spec = component["spec"]
        expected_type = (
            "service" if workload_kinds[workload_name] == "service" else "job"
        )

        assert spec["owner"] == f"group:default/{workload_owners[workload_name]}"
        assert spec["system"] == "aws-sdlc-containers"
        assert spec["type"] == expected_type
        assert spec["lifecycle"] == "experimental"
        assert spec["dependsOn"] == workload_runtime_dependencies[workload_name]
        assert component["metadata"]["tags"] == workload_use_cases[workload_name]
