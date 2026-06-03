from __future__ import annotations

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

    assert {"edge_auth", "service_identity", "runtime_policy"}.issubset(capabilities)


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
