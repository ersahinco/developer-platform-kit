from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from scripts.ci.workflow_dry_run_commands import workflow_dispatch_inputs

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_BACKSTAGE_WORKFLOW_ACTIONS = {
    "app-build.yml",
    "app-deploy.yml",
    "infra-plan.yml",
    "infra-apply.yml",
    "data-schema-apply.yml",
    "data-runtime-switch.yml",
    "data-backfill.yml",
    "data-support-deploy.yml",
    "operational-snapshot.yml",
}


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
    support = json.loads(
        (ROOT / "platform" / "workload-runtime-support.json").read_text()
    )["targets"]
    active_targets = set(
        json.loads((ROOT / "platform" / "runtime-defaults.json").read_text())[
            "runtime_targets"
        ]
    )
    dependencies: dict[str, list[str]] = {}
    for workload in workloads:
        if not isinstance(workload, dict):
            continue
        name = workload.get("name")
        if not isinstance(name, str):
            continue
        supported = [
            target
            for target, profile in support.items()
            if target in active_targets and name in profile["supported_workloads"]
        ]
        dependencies[name] = [
            f"resource:default/runtime-target-{runtime_target}"
            for runtime_target in supported
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
    assert ("Resource", "runtime-target-hetzner-compose") in entities
    assert ("Resource", "delivery-edge-coolify") in entities
    assert ("Resource", "network-edge-netbird") in entities
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
    assert annotations["aws-sdlc-containers/integration-mode"] == "read-and-dispatch"
    assert annotations["aws-sdlc-containers/mutation-gateway"] == "github-actions"
    assert (
        annotations["aws-sdlc-containers/placement-source"]
        == "platform/workload-runtime-support.json"
    )
    assert (
        annotations["aws-sdlc-containers/observed-deployment-source"]
        == "scripts/observability/release_event.py"
    )


def test_backstage_actions_dispatch_only_declared_github_workflows() -> None:
    templates = {
        document["metadata"]["annotations"]["aws-sdlc-containers/workflow-id"]: document
        for document in _load_catalog_entity_documents()
        if document.get("kind") == "Template"
    }

    assert set(templates) == EXPECTED_BACKSTAGE_WORKFLOW_ACTIONS

    for workflow_id, template in templates.items():
        metadata = template["metadata"]
        annotations = metadata["annotations"]
        steps = template["spec"]["steps"]
        assert template["apiVersion"] == "scaffolder.backstage.io/v1beta3"
        assert template["spec"]["owner"] == "group:default/platform-engineering"
        assert annotations["github.com/project-slug"] == (
            "ersahinco/aws-sdlc-containers"
        )
        assert annotations["aws-sdlc-containers/mutation-gateway"] == ("github-actions")
        assert len(steps) == 1

        dispatch = steps[0]
        dispatch_input = dispatch["input"]
        assert dispatch["action"] == "github:actions:dispatch"
        assert dispatch_input["repoUrl"] == (
            "${{ environment.parameters.deliveryRepoUrl }}"
        )
        assert dispatch_input["workflowId"] == workflow_id
        assert dispatch_input["branchOrTagName"] == "main"

        workflow_path = ROOT / ".github" / "workflows" / workflow_id
        declared_inputs = workflow_dispatch_inputs(workflow_path)
        dispatched_inputs = set(dispatch_input.get("workflowInputs", {}))
        parameter_inputs = {
            name
            for group in template["spec"].get("parameters", [])
            for name in group.get("properties", {})
        }
        assert dispatched_inputs == declared_inputs
        assert parameter_inputs == declared_inputs

        if "dry_run" in declared_inputs:
            dry_run_properties = [
                group["properties"]["dry_run"]
                for group in template["spec"]["parameters"]
                if "dry_run" in group.get("properties", {})
            ]
            assert dry_run_properties == [
                {
                    "title": "Dry run",
                    "type": "string",
                    "default": "true",
                    "enum": ["true", "false"],
                }
            ]


def test_platform_edge_candidates_have_no_active_mutation_authority() -> None:
    resources = {
        document["metadata"]["name"]: document
        for document in _load_catalog_entity_documents()
        if document.get("kind") == "Resource"
    }
    coolify = resources["delivery-edge-coolify"]["metadata"]["annotations"]
    netbird = resources["network-edge-netbird"]["metadata"]["annotations"]

    assert coolify["aws-sdlc-containers/status"] == "bounded-experiment"
    assert coolify["aws-sdlc-containers/authority"] == "none-until-admitted"
    assert netbird["aws-sdlc-containers/status"] == "bounded-candidate"
    assert netbird["aws-sdlc-containers/authority"] == "none-until-admitted"
    assert netbird["aws-sdlc-containers/public-dns-authority"] == "terraform"

    candidate_refs = {
        "resource:default/delivery-edge-coolify",
        "resource:default/network-edge-netbird",
    }
    dependencies = {
        dependency
        for document in _load_catalog_entity_documents()
        for dependency in document.get("spec", {}).get("dependsOn", [])
    }
    assert candidate_refs.isdisjoint(dependencies)


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
