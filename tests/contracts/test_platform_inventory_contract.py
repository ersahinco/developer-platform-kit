from __future__ import annotations

from ._helpers import load_json, read_text


def test_platform_inventory_has_required_shape() -> None:
    inventory = load_json("platform/platform-inventory.json")

    assert inventory["schema_version"] == "1"
    assert inventory["stable_center"] == {
        "workload_contract": "platform/workloads.json",
        "platform_concerns_root": "platform/concerns",
        "catalog_root": "infra/catalog",
    }
    assert inventory["current_runtime_target"] == "aws-ecs"
    assert isinstance(inventory["runtime_targets"], list)
    assert {target["id"] for target in inventory["runtime_targets"]} == {
        "local-compose",
        "aws-ecs",
        "managed-service-provider",
    }
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
    assert any(
        row["capability"] == "local_runtime"
        and row["runtime_target"] == "local-compose"
        and "platform/runtime-conformance.json" in row["replacement_seam"]
        for row in runtime_capabilities
    )


def test_current_aws_runtime_realizes_all_aws_admitted_job_workloads() -> None:
    contract = load_json("platform/workloads.json")
    workload_jobs_text = read_text("infra/app/workload_jobs.tf")

    deployable_jobs = [
        workload["name"]
        for workload in contract["workloads"]
        if workload["kind"] == "job" and "aws-ecs" in workload["runtime"]["admitted"]
    ]

    for workload_name in deployable_jobs:
        assert f"{workload_name} =" in workload_jobs_text


def test_aws_runtime_inventory_filters_out_non_admitted_workloads() -> None:
    contract = load_json("platform/workloads.json")
    workload_inventory_text = read_text("infra/app/workload_inventory.tf")

    assert "aws_admitted_workloads" in workload_inventory_text
    assert 'contains(try(workload.runtime.admitted, []), "aws-ecs")' in (
        workload_inventory_text
    )
    assert (
        "for workload in local.aws_admitted_workloads : workload.name => workload"
        in (workload_inventory_text)
    )

    non_admitted_workloads = [
        workload["name"]
        for workload in contract["workloads"]
        if "aws-ecs" not in workload["runtime"]["admitted"]
    ]
    for workload_name in non_admitted_workloads:
        assert f'"{workload_name}"' not in workload_inventory_text


def test_aws_runtime_inventory_keeps_app_default_tuning_out_of_platform_defaults() -> (
    None
):
    workload_inventory_text = read_text("infra/app/workload_inventory.tf")

    assert "BACKFILL_BATCH_SIZE" not in workload_inventory_text
    assert "BACKFILL_SLEEP_MS" not in workload_inventory_text
    assert "DATA_EXPORT_OUTPUT_DIR" not in workload_inventory_text
    assert "EVENT_CONSUMER_WORKER_MODE" not in workload_inventory_text
    assert "EVENT_CONSUMER_RELAY_BATCH_SIZE" not in workload_inventory_text
    assert "EVENT_CONSUMER_IDLE_SLEEP_SECONDS" not in workload_inventory_text
