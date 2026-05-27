from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_workload_contract_docs_name_workloads_json_as_canonical_intent_source() -> (
    None
):
    platform_contract = _read("docs/platform-contract.md")
    platform_readme = _read("platform/README.md")

    assert "canonical definition of workload intent" in platform_contract
    assert "`platform/workloads.json` is the machine-readable workload contract" in (
        platform_contract
    )
    assert "`workloads.json`: canonical workload contract" in platform_readme
    assert (
        "`platform/workload-patterns.json` is the machine-readable list of supported"
        in platform_contract
    )
    assert "`workload-patterns.json`: supported workload classification shapes" in (
        platform_readme
    )


def test_platform_inventory_file_is_part_of_stable_center() -> None:
    platform_readme = _read("platform/README.md")

    assert "`platform-inventory.json`: canonical static platform inventory" in (
        platform_readme
    )


def test_runtime_realization_layers_do_not_replace_stable_center() -> None:
    agents = _read("AGENTS.md")
    architecture = _read("docs/architecture.md")
    runtime_toolkit = _read("docs/runtime-toolkit.md")

    assert "Add future runtime targets as parallel realization layers" in agents
    assert "Runtime targets are pluggable" in architecture
    assert "realizations at the platform edge" in architecture
    assert "`platform/workloads.json` is the machine-readable workload contract" in (
        runtime_toolkit
    )
    assert "existing workload intent remains recognizable without reinvention" in (
        runtime_toolkit
    )
    assert "application spec" not in runtime_toolkit


def test_catalog_growth_rule_uses_runtime_target_subdirectories() -> None:
    infra_readme = _read("infra/README.md")
    catalog_readme = _read("infra/catalog/README.md")
    aws_catalog = _read("infra/catalog/aws/README.md")
    managed_service_provider_catalog = (
        ROOT / "infra" / "catalog" / "managed-service-provider" / "README.md"
    )

    assert "infra/catalog/<runtime-target>/" in infra_readme
    assert (
        "Organize the catalog by runtime target under `infra/catalog/<runtime-target>/`"
        in (catalog_readme)
    )
    assert "Future runtime targets should" in aws_catalog
    assert "`infra/catalog/<runtime-target>/`" in aws_catalog
    assert managed_service_provider_catalog.is_file()


def test_docs_do_not_forbid_additional_runtime_targets_in_principle() -> None:
    agents = _read("AGENTS.md")
    runtime_toolkit = _read("docs/runtime-toolkit.md")
    roadmap = _read("docs/roadmaps.md")

    assert "A second cloud/runtime target" not in agents
    assert "Do not add a second runtime just to prove portability." not in (
        runtime_toolkit
    )
    assert "Second runtime target" not in roadmap


def test_docs_describe_adapter_first_portability_strategy() -> None:
    packages_readme = _read("packages/README.md")
    packages_agents = _read("packages/AGENTS.md")
    runtime_toolkit = _read("docs/runtime-toolkit.md")
    platform_capabilities = _read("docs/platform-capabilities.md")

    assert (
        "Future runtime replacements should prefer adding or swapping infrastructure adapters"
        in (packages_agents)
    )
    assert "add future runtime adapters at the same seam" in packages_readme
    assert "Prefer portability through explicit adapters and replacement seams" in (
        runtime_toolkit
    )
    assert (
        "Rule: add or swap adapters and runtime-target realization code before changing"
        in (platform_capabilities)
    )


def test_docs_define_contract_admission_rule() -> None:
    platform_capabilities = _read("docs/platform-capabilities.md")

    assert (
        "admit a capability only when it has contract shape, local proof, runtime realization, delivery path, and owner"
        in platform_capabilities
    )


def test_docs_define_local_to_aws_admission_order() -> None:
    adding_workloads = _read("docs/adding-workloads.md")
    deployment = _read("docs/deployment.md")
    platform_contract = _read("docs/platform-contract.md")

    assert "## Promote Local To AWS" in adding_workloads
    assert "Rule: local proof comes first, cloud admission comes second." in (
        adding_workloads
    )
    assert "## Admitting A Local Workload To AWS" in deployment
    assert (
        "Declare a portable workload owner before adding cloud runtime admission"
        in (platform_contract)
    )
