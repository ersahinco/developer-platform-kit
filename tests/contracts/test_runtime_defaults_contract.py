from __future__ import annotations

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

ACTIVE_EVIDENCE_SEAMS = {
    ("local-compose", "authz_policy"): ["platform/concerns/policy"],
    ("local-compose", "ci_cd_delivery"): ["Makefile", "tests/runtime"],
    ("local-compose", "network_connectivity"): [
        "compose.yaml",
        "platform/runtime-conformance.json",
    ],
    ("local-compose", "observability_routing"): [
        "platform/concerns/observability",
        "compose.yaml",
    ],
    ("aws-ecs", "authz_policy"): ["platform/concerns/policy"],
    ("aws-ecs", "ci_cd_delivery"): [
        ".github/workflows",
        "infra/platform/github_actions.tf",
    ],
    ("aws-ecs", "network_connectivity"): [
        "infra/platform/network.tf",
        "infra/app/edge.tf",
    ],
    ("aws-ecs", "observability_routing"): [
        "infra/app/observability.tf",
        "scripts/observability",
    ],
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


def test_enterprise_runtime_profile_is_candidate_not_active_target() -> None:
    inventory = load_json("platform/platform-inventory.json")
    runtime_defaults = load_json("platform/runtime-defaults.json")

    active_targets = {target["id"] for target in inventory["runtime_targets"]}
    candidates = runtime_defaults["candidate_runtime_profiles"]

    assert "enterprise-runtime-candidate" in candidates
    assert "enterprise-runtime-candidate" not in active_targets
    assert candidates["enterprise-runtime-candidate"]["status"] == "candidate"


def test_runtime_capabilities_include_enterprise_relevant_defaults() -> None:
    inventory = load_json("platform/platform-inventory.json")
    capabilities = {item["capability"] for item in inventory["runtime_capabilities"]}

    assert {
        "authz_policy",
        "ci_cd_delivery",
        "edge_auth",
        "network_connectivity",
        "observability_routing",
        "runtime_policy",
        "service_identity",
    }.issubset(capabilities)


def test_active_runtime_defaults_are_backed_by_capability_rows() -> None:
    inventory = load_json("platform/platform-inventory.json")
    runtime_defaults = load_json("platform/runtime-defaults.json")

    capability_pairs = {
        (row["runtime_target"], row["capability"])
        for row in inventory["runtime_capabilities"]
    }

    for runtime_target, profile in runtime_defaults["runtime_targets"].items():
        for area, default in profile["defaults"].items():
            pair = (runtime_target, default["capability"])
            assert pair in capability_pairs, (
                f"{runtime_target}.{area} default points at {pair}, "
                "but platform/platform-inventory.json has no active capability row"
            )


def test_enterprise_candidate_defaults_are_candidate_capabilities_only() -> None:
    inventory = load_json("platform/platform-inventory.json")
    runtime_defaults = load_json("platform/runtime-defaults.json")

    candidate_pairs = {
        (row["runtime_target"], row["capability"])
        for row in inventory["candidate_runtime_capabilities"]
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


def test_active_capability_rows_point_to_real_evidence_seams() -> None:
    inventory = load_json("platform/platform-inventory.json")
    active_capabilities = {
        (row["runtime_target"], row["capability"]): row
        for row in inventory["runtime_capabilities"]
    }

    for pair, expected_paths in ACTIVE_EVIDENCE_SEAMS.items():
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

    assert "[Runtime Defaults](runtime-defaults.md)" in runtime_toolkit
    assert "platform/runtime-defaults.json" in runtime_defaults_doc
    assert "enterprise-runtime-candidate" in runtime_defaults_doc
