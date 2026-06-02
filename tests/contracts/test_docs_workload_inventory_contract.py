from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_canonical_docs_delegate_live_workload_inventory_to_contract() -> None:
    platform_contract = _read("docs/platform-contract.md")
    architecture = _read("docs/architecture.md")
    local_development = _read("docs/local-development.md")

    assert "The current workload inventory lives in `platform/workloads.json`" in (
        platform_contract
    )
    assert "The current class mapping is declared per workload" in platform_contract
    assert "Current long-running workloads:" not in platform_contract
    assert "Current jobs:" not in platform_contract
    assert "Current mapping:" not in platform_contract
    assert "Current mappings live\nin `platform/workloads.json`" in architecture
    assert "Reference workloads:" not in local_development
    assert "make workload-readiness" in local_development
    assert "make workload-addition-report" in local_development
