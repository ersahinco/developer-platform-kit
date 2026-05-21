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


def test_catalog_info_declares_backstage_location_for_platform_entities() -> None:
    documents = _load_yaml_documents("catalog-info.yaml")
    assert len(documents) == 1
    location = documents[0]

    assert location["kind"] == "Location"
    assert location["metadata"]["name"] == "aws-sdlc-containers-catalog"
    assert location["spec"]["type"] == "file"
    assert sorted(location["spec"]["targets"]) == sorted(
        [
            "./catalog/platform-engineering-group.yaml",
            "./catalog/platform-engineering-domain.yaml",
            "./catalog/aws-sdlc-containers-system.yaml",
            "./catalog/runtime-target-aws-ecs.yaml",
            "./catalog/platform-monorepo-component.yaml",
            "./catalog/api-component.yaml",
            "./catalog/event-consumer-component.yaml",
            "./catalog/backfill-worker-component.yaml",
            "./catalog/data-export-job-component.yaml",
            "./catalog/open-dataset-pipeline-component.yaml",
        ]
    )


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
    assert ("Resource", "runtime-target-aws-ecs") in entities
    assert ("Component", "platform-monorepo") in entities


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
    workload_use_cases = _load_workload_use_cases()

    assert sorted(component_entities) == sorted(workload_names)

    for workload_name in workload_names:
        component = component_entities[workload_name]
        spec = component["spec"]
        expected_type = (
            "service" if workload_kinds[workload_name] == "service" else "job"
        )

        assert spec["owner"] == "group:default/platform-engineering"
        assert spec["system"] == "aws-sdlc-containers"
        assert spec["type"] == expected_type
        assert spec["lifecycle"] == "experimental"
        assert spec["dependsOn"] == ["resource:default/runtime-target-aws-ecs"]
        assert component["metadata"]["tags"] == workload_use_cases[workload_name]
