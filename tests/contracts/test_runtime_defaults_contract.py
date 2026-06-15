from __future__ import annotations

from scripts.platform.workload_metadata import current_runtime_capability_rows

from ._helpers import ROOT
from ._helpers import load_json
from ._helpers import read_text


REQUIRED_DEFAULT_AREAS = {
    "authn",
    "authz",
    "ci_cd",
    "network",
    "observability",
    "policy",
    "secrets",
    "service_identity",
}

DEFAULT_AREA_CAPABILITIES = {
    "authn": "edge_auth",
    "authz": "authz_policy",
    "ci_cd": "ci_cd_delivery",
    "network": "network_connectivity",
    "observability": "observability_routing",
    "policy": "runtime_policy",
    "secrets": "secrets_injection",
    "service_identity": "service_identity",
}

ENTERPRISE_RELEVANT_CAPABILITIES = {
    "authz_policy",
    "ci_cd_delivery",
    "edge_auth",
    "network_connectivity",
    "observability_routing",
}

CAPABILITY_MATURITY_LEVELS = {
    "candidate",
    "active-local-proof",
    "active-production-runtime",
    "deprecated",
}

EXTRA_EVIDENCE_SEAMS = {
    ("local-compose", "local_runtime"): [
        "compose.yaml",
        "platform/runtime-conformance.json",
    ],
    ("local-kubernetes", "local_runtime"): [
        "infra/local-kubernetes",
        "platform/workloads.json",
        "platform/runtime-conformance.json",
    ],
    ("local-kubernetes", "local_rollout_proof"): [
        "Makefile",
        "scripts/platform/local_kubernetes_proof.py",
        "tests/scripts/test_local_kubernetes_proof.py",
    ],
    ("local-kubernetes", "local_dapr_eventing_proof"): [
        "Makefile",
        "scripts/platform/local_kubernetes_proof.py",
        "infra/local-kubernetes",
        "tests/contracts/test_local_kubernetes_contract.py",
    ],
    ("local-kubernetes", "local_evidence_drill"): [
        "Makefile",
        "scripts/platform/local_kubernetes_proof.py",
        "tests/contracts/test_documented_make_targets.py",
    ],
    ("aws-ecs", "edge_http"): [
        "infra/app/edge.tf",
        ".github/workflows/app-deploy.yml",
    ],
    ("aws-ecs", "relational_database"): [
        "infra/app/database.tf",
        "infra/app/workload_inventory.tf",
    ],
    ("aws-ecs", "async_eventing"): [
        "platform/concerns/dapr",
        "infra/app/messaging.tf",
    ],
    ("aws-ecs", "scheduled_execution"): ["infra/app/workload_jobs.tf"],
    ("aws-ecs", "operator_job_execution"): [
        ".github/workflows/data-backfill.yml",
        ".github/workflows/operational-snapshot.yml",
        "infra/app/workload_jobs.tf",
    ],
    ("aws-ecs", "object_storage"): ["infra/app/object_storage.tf"],
    ("aws-ecs", "tracing"): [
        "infra/app/observability.tf",
        "infra/app/workload_inventory.tf",
    ],
    ("aws-ecs", "release_evidence"): ["scripts/observability/release_event.py"],
}


def test_active_runtime_targets_have_blessed_defaults() -> None:
    inventory = load_json("platform/platform-inventory.json")
    runtime_defaults = load_json("platform/runtime-defaults.json")

    active_targets = {target["id"] for target in inventory["runtime_targets"]}
    default_targets = runtime_defaults["runtime_targets"]

    assert set(default_targets) == active_targets
    for runtime_target, profile in default_targets.items():
        assert profile["status"] == "active"
        assert profile["owner"]
        defaults = profile["defaults"]
        assert set(defaults) == REQUIRED_DEFAULT_AREAS
        for area, default in defaults.items():
            assert default["capability"] == DEFAULT_AREA_CAPABILITIES[area], (
                f"{runtime_target}.{area} points at the wrong capability"
            )
            assert default["default"], f"{runtime_target}.{area} lacks a default"
            assert default["realization"], f"{runtime_target}.{area} lacks realization"
            assert default["evidence"], f"{runtime_target}.{area} lacks evidence"


def test_runtime_capability_maturity_is_explicit_and_consistent() -> None:
    inventory = load_json("platform/platform-inventory.json")
    runtime_defaults = load_json("platform/runtime-defaults.json")

    target_maturity = {
        target["id"]: target["maturity"] for target in inventory["runtime_targets"]
    }
    assert target_maturity == {
        "local-compose": "active-local-proof",
        "local-kubernetes": "active-local-proof",
        "aws-ecs": "active-production-runtime",
    }
    assert set(target_maturity.values()) <= CAPABILITY_MATURITY_LEVELS

    for row in inventory["runtime_capabilities"]:
        assert row["maturity"] in CAPABILITY_MATURITY_LEVELS
        assert row["maturity"] == target_maturity[row["runtime_target"]]

    for profile in runtime_defaults["candidate_runtime_profiles"].values():
        assert profile["status"] == "candidate"


def test_enterprise_runtime_profile_is_candidate_not_active_target() -> None:
    inventory = load_json("platform/platform-inventory.json")
    runtime_defaults = load_json("platform/runtime-defaults.json")

    active_targets = {target["id"] for target in inventory["runtime_targets"]}
    candidates = runtime_defaults["candidate_runtime_profiles"]

    assert "enterprise-runtime-candidate" in candidates
    assert "enterprise-runtime-candidate" not in active_targets
    assert candidates["enterprise-runtime-candidate"]["status"] == "candidate"


def test_runtime_defaults_include_enterprise_relevant_capabilities() -> None:
    runtime_defaults = load_json("platform/runtime-defaults.json")
    capabilities = {
        default["capability"]
        for profile in runtime_defaults["runtime_targets"].values()
        for default in profile["defaults"].values()
    }

    assert {
        "authz_policy",
        "ci_cd_delivery",
        "edge_auth",
        "network_connectivity",
        "observability_routing",
        "runtime_policy",
        "service_identity",
    }.issubset(capabilities)


def test_active_runtime_defaults_are_derived_not_duplicated() -> None:
    inventory = load_json("platform/platform-inventory.json")
    runtime_defaults = load_json("platform/runtime-defaults.json")

    inventory_pairs = {
        (row["runtime_target"], row["capability"])
        for row in inventory["runtime_capabilities"]
    }
    matrix_pairs = {
        (row["runtime_target"], row["capability"])
        for row in current_runtime_capability_rows()
    }

    for runtime_target, profile in runtime_defaults["runtime_targets"].items():
        for area, default in profile["defaults"].items():
            pair = (runtime_target, default["capability"])
            assert pair not in inventory_pairs, (
                f"{runtime_target}.{area} default is duplicated in "
                "platform/platform-inventory.json"
            )
            assert pair in matrix_pairs


def test_enterprise_candidate_defaults_are_candidate_capabilities_only() -> None:
    inventory = load_json("platform/platform-inventory.json")
    runtime_defaults = load_json("platform/runtime-defaults.json")

    candidate_pairs = {
        (runtime_target, default["capability"])
        for runtime_target, profile in runtime_defaults[
            "candidate_runtime_profiles"
        ].items()
        for default in profile["defaults"].values()
    }
    active_pairs = {
        (row["runtime_target"], row["capability"])
        for row in inventory["runtime_capabilities"]
    }
    candidates = runtime_defaults["candidate_runtime_profiles"]

    enterprise = candidates["enterprise-runtime-candidate"]
    for area, default in enterprise["defaults"].items():
        assert default["capability"] == DEFAULT_AREA_CAPABILITIES[area]
        assert (
            "enterprise-runtime-candidate",
            default["capability"],
        ) in candidate_pairs
        assert (
            "enterprise-runtime-candidate",
            default["capability"],
        ) not in active_pairs

    candidate_capabilities = {
        capability
        for runtime_target, capability in candidate_pairs
        if runtime_target == "enterprise-runtime-candidate"
    }
    assert ENTERPRISE_RELEVANT_CAPABILITIES.issubset(candidate_capabilities)


def test_candidate_runtime_profiles_stay_descriptive() -> None:
    inventory = load_json("platform/platform-inventory.json")
    runtime_defaults = load_json("platform/runtime-defaults.json")

    active_targets = {target["id"] for target in inventory["runtime_targets"]}
    for runtime_target, profile in runtime_defaults[
        "candidate_runtime_profiles"
    ].items():
        assert runtime_target not in active_targets
        assert profile["status"] == "candidate"
        assert profile["owner"] == "future-runtime-owner-required"
        for default in profile["defaults"].values():
            assert default["capability"]
            assert default["default"]
            assert default["realization"]
            assert default["evidence"]
            assert "infra/" not in default["realization"]


def test_extra_capability_rows_point_to_real_evidence_seams() -> None:
    inventory = load_json("platform/platform-inventory.json")
    active_capabilities = {
        (row["runtime_target"], row["capability"]): row
        for row in inventory["runtime_capabilities"]
    }

    for pair, expected_paths in EXTRA_EVIDENCE_SEAMS.items():
        row = active_capabilities[pair]
        replacement_seam = row["replacement_seam"]
        for expected_path in expected_paths:
            assert expected_path in replacement_seam
            assert (ROOT / expected_path).exists()


def test_workload_metadata_does_not_embed_runtime_tool_fields() -> None:
    workloads_text = read_text("platform/workloads.json").lower()
    runtime_defaults = load_json("platform/runtime-defaults.json")

    for forbidden in runtime_defaults["forbidden_workload_tool_fields"]:
        assert forbidden.lower() not in workloads_text


def test_runtime_defaults_are_documented() -> None:
    runtime_toolkit = read_text("docs/runtime-toolkit.md")
    runtime_defaults_doc = read_text("docs/runtime-defaults.md")
    platform_contract = read_text("docs/platform-contract.md")
    security_concern = read_text("platform/concerns/security/README.md")
    networking_concern = read_text("platform/concerns/networking/README.md")

    assert "[Runtime Defaults](runtime-defaults.md)" in runtime_toolkit
    assert "platform/runtime-defaults.json" in runtime_defaults_doc
    assert "enterprise-runtime-candidate" in runtime_defaults_doc
    assert "candidate runtime profiles" in platform_contract
    assert "candidate capability rows" not in platform_contract
    assert "platform/runtime-defaults.json" in security_concern
    assert "platform/runtime-defaults.json" in networking_concern
