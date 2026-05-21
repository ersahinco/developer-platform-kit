from __future__ import annotations

from ._helpers import load_json


def test_platform_inventory_has_required_shape() -> None:
    inventory = load_json("platform/platform-inventory.json")

    assert inventory["schema_version"] == "1"
    assert inventory["stable_center"] == {
        "workload_contract": "platform/workloads.json",
        "platform_concerns_root": "platform/concerns",
        "catalog_root": "infra/catalog",
    }
    assert inventory["current_runtime_target"] == "aws-ecs"
    assert isinstance(inventory["runtime_capabilities"], list)
    assert isinstance(inventory["adapter_seams"], list)
    assert inventory["runtime_capabilities"]
    assert inventory["adapter_seams"]


def test_platform_inventory_rows_reference_expected_stable_center_seams() -> None:
    inventory = load_json("platform/platform-inventory.json")

    runtime_capabilities = inventory["runtime_capabilities"]
    adapter_seams = inventory["adapter_seams"]

    assert any(
        row["capability"] == "relational_database"
        and "infra/app/database.tf" in row["replacement_seam"]
        for row in runtime_capabilities
    )
    assert any(
        row["capability"] == "async_eventing"
        and row["adapter_seam"] == "packages/infrastructure/dapr/"
        for row in adapter_seams
    )
