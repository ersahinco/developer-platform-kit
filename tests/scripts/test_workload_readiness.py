from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.platform.workload_readiness import readiness_rows
from scripts.platform.workload_readiness import readiness_failures
from scripts.platform.workload_readiness import addition_rows
from scripts.platform.workload_readiness import _catalog_targets
from scripts.platform.workload_readiness import _compose_service_names
from scripts.platform.workload_readiness import _evidence
from scripts.platform.workload_readiness import _policy_delivery_gate


ROOT = Path(__file__).resolve().parents[2]


def test_workload_readiness_reports_all_declared_workloads() -> None:
    contract = json.loads((ROOT / "platform" / "workloads.json").read_text())

    rows = readiness_rows()

    assert [row["workload"] for row in rows] == [
        workload["name"] for workload in contract["workloads"]
    ]


def test_workload_addition_report_shows_current_wiring_surfaces() -> None:
    rows = {row["workload"]: row for row in addition_rows()}

    assert rows["api"]["app_files"] == "ok"
    assert rows["api"]["app_tests"] == "yes"
    assert rows["support_triage_llm"]["compose_service"] == "yes"
    assert rows["support_triage_llm"]["catalog_component"] == "yes"
    assert rows["support_triage_llm"]["runtime_conformance"] == "yes"


def test_workload_addition_report_reads_compose_and_catalog_shapes() -> None:
    compose_services = _compose_service_names(ROOT / "compose.yaml")
    catalog_targets = _catalog_targets(ROOT / "catalog-info.yaml")

    assert "support-triage-llm" in compose_services
    assert "catalog/support-triage-llm-component.yaml" in catalog_targets


def test_workload_addition_report_reads_yaml_shapes(tmp_path) -> None:
    compose = tmp_path / "compose.yaml"
    compose.write_text(
        """
name: example
services:
  api:
    image: example-api
  worker:
    profiles: ["jobs"]
networks:
  default: {}
""",
        encoding="utf-8",
    )
    catalog = tmp_path / "catalog-info.yaml"
    catalog.write_text(
        """
apiVersion: backstage.io/v1alpha1
kind: Location
spec:
  targets:
    - ./catalog/api-component.yaml
    - catalog/worker-component.yaml
""",
        encoding="utf-8",
    )

    assert _compose_service_names(compose) == {"api", "worker"}
    assert _catalog_targets(catalog) == {
        "catalog/api-component.yaml",
        "catalog/worker-component.yaml",
    }


def test_workload_readiness_shows_paved_road_surfaces() -> None:
    rows = {row["workload"]: row for row in readiness_rows()}

    assert rows["api"]["service_endpoints"] == "/health,/ready,/metrics"
    assert rows["api"]["owner"] == "platform-engineering"
    assert rows["api"]["use_cases"] == "http-api"
    assert rows["api"]["logs_contract"] == (
        "http_request:event,request_id,route,status_code"
    )
    assert rows["api"]["metrics_contract"] == (
        "workload_info,http_requests_total,http_request_duration_seconds"
    )
    assert rows["api"]["secret_names"] == "DB_PASSWORD,PRIMARY_EDGE_AUTH_TOKEN"
    assert rows["api"]["secret_injection"] == ("local-compose,local-kubernetes,aws-ecs")
    assert "DATABASE_URL" in rows["api"]["config_env"].split(",")
    assert rows["api"]["config_realization"] == (
        "local-compose,local-kubernetes,aws-ecs"
    )
    assert rows["api"]["local_compose"] == "yes"
    assert rows["api"]["local_kubernetes"] == "yes"
    assert rows["api"]["aws_ecs_supported"] == "yes"
    assert rows["api"]["aws_ecs_admitted"] == "yes"
    assert rows["api"]["policy_delivery_gate"] == "platform-toolkit-validate-cloud"
    assert rows["api"]["local_kubernetes_admission"] == "ready"
    assert "local-kubernetes-evidence-drill" in rows["api"]["proof_surface"]
    assert "aws-ecs-evidence" in rows["api"]["proof_surface"]
    assert rows["api"]["run_workflow"] == "app-deploy.yml"
    assert rows["api"]["evidence"] == "app-deploy.yml"
    assert rows["api"]["rollback_proof"] == "app_image"
    assert rows["event_consumer"]["run_workflow"] == "app-deploy.yml"
    assert rows["event_consumer"]["use_cases"] == "event-consumer,integration"
    assert rows["event_consumer"]["eventing_contract"] == (
        "async-events-pubsub:async-events-v1.fifo"
    )
    assert "DAPR_TOPIC" in rows["event_consumer"]["config_env"].split(",")
    assert rows["event_consumer"]["config_realization"] == (
        "local-compose,local-kubernetes,aws-ecs"
    )
    assert rows["event_consumer"]["evidence"] == "app-deploy.yml"
    assert rows["event_consumer"]["rollback_proof"] == "app_image"
    assert rows["backfill_worker"]["idempotency_contract"] == "checkpointed"
    assert rows["backfill_worker"]["logs_contract"] == (
        "backfill_complete:event,job_name"
    )
    assert rows["backfill_worker"]["run_workflow"] == "data-backfill.yml"
    assert "data-backfill.yml" in rows["backfill_worker"]["evidence"]
    assert rows["backfill_worker"]["rollback_proof"] == "runtime_data_phase"
    assert rows["data_export_job"]["run_workflow"] == "data-support-deploy.yml"
    assert rows["data_export_job"]["evidence"] == "data-support-deploy.yml"
    assert rows["data_export_job"]["rollback_proof"] == "support_task_image"
    assert rows["operational_snapshot_job"]["run_workflow"] == (
        "operational-snapshot.yml"
    )
    assert "operational-snapshot.yml" in rows["operational_snapshot_job"]["evidence"]
    assert rows["operational_snapshot_job"]["rollback_proof"] == (
        "runtime_observability"
    )
    assert rows["integration_check_job"]["run_workflow"] == "not-aws-admitted"
    assert rows["integration_check_job"]["log_group"] == "not-aws-admitted"
    assert rows["integration_check_job"]["rollback_proof"] == "not-aws-admitted"
    assert rows["integration_check_job"]["policy_delivery_gate"] == "not-aws-supported"
    assert rows["integration_check_job"]["config_realization"] == (
        "local-compose,local-kubernetes"
    )
    assert rows["integration_check_job"]["secret_injection"] == "none"
    assert (
        "local-kubernetes-evidence-drill"
        in rows["integration_check_job"]["proof_surface"]
    )
    assert rows["integration_check_job"]["job_terminal_event"] == (
        "integration_check_succeeded"
    )
    assert rows["open_dataset_pipeline"]["run_workflow"] == "not-aws-admitted"
    assert rows["foreign_inventory_sync"]["run_workflow"] == "not-aws-admitted"
    assert rows["foreign_inventory_sync"]["evidence"] == "n/a"
    assert rows["foreign_inventory_sync"]["rollback_proof"] == "not-aws-admitted"


def test_workload_readiness_counts_only_runtime_evidence_for_services() -> None:
    edge_workload = {
        "name": "api",
        "kind": "service",
        "operational": {"class": "edge-service"},
        "image": {"repository": "api"},
    }
    internal_workload = {
        "name": "event_consumer",
        "kind": "service",
        "operational": {"class": "internal-service"},
        "image": {"repository": "event-consumer"},
    }
    edge_workflow_texts = {
        "app-build.yml": "api release-evidence-app-build",
        "app-deploy.yml": "release-evidence-app-deploy",
    }
    app_host_set_workflow_texts = {
        "app-deploy.yml": (
            "release-evidence-app-deploy app_host_workloads --related-workload-id"
        ),
    }

    assert (
        _evidence(
            edge_workload,
            workflow_texts=edge_workflow_texts,
            aws_admitted=True,
        )
        == "app-deploy.yml"
    )
    assert (
        _evidence(
            internal_workload,
            workflow_texts=edge_workflow_texts,
            aws_admitted=True,
        )
        == "n/a"
    )
    assert (
        _evidence(
            internal_workload,
            workflow_texts=app_host_set_workflow_texts,
            aws_admitted=True,
        )
        == "app-deploy.yml"
    )


def test_policy_delivery_gate_distinguishes_aws_admission_states() -> None:
    assert (
        _policy_delivery_gate(aws_supported=True, aws_admitted=True)
        == "platform-toolkit-validate-cloud"
    )
    assert (
        _policy_delivery_gate(aws_supported=True, aws_admitted=False)
        == "aws-admission-required"
    )
    assert (
        _policy_delivery_gate(aws_supported=False, aws_admitted=False)
        == "not-aws-supported"
    )


def test_workload_readiness_requires_targeted_support_evidence() -> None:
    workload = {
        "name": "data_export_job",
        "kind": "job",
        "operational": {"class": "scheduled-job"},
        "image": {"repository": "data-export-job"},
    }
    aggregate_workflow_texts = {
        "data-support-deploy.yml": (
            "release-evidence-data-support-deploy "
            "--workload-id support-tasks target_workload"
        )
    }
    targeted_workflow_texts = {
        "data-support-deploy.yml": (
            "release-evidence-data-support-deploy "
            'evidence_workload_id="${{ inputs.target_workload }}" '
            '--workload-id "$evidence_workload_id"'
        )
    }

    assert (
        _evidence(
            workload,
            workflow_texts=aggregate_workflow_texts,
            aws_admitted=True,
        )
        == "n/a"
    )
    assert (
        _evidence(
            workload,
            workflow_texts=targeted_workflow_texts,
            aws_admitted=True,
        )
        == "data-support-deploy.yml"
    )


def test_workload_readiness_cli_outputs_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_readiness.py",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    rows = json.loads(completed.stdout)
    assert rows[0]["workload"] == "api"
    assert "run_workflow" in rows[0]


def test_workload_readiness_cli_outputs_summary_view() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_readiness.py",
            "--view",
            "summary",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    lines = completed.stdout.splitlines()
    assert lines[0].split("\t") == [
        "workload",
        "kind",
        "class",
        "owner",
        "use_cases",
        "local_proof",
        "aws_ecs",
        "proof_surface",
        "proof_command",
    ]
    assert "local-compose+local-kubernetes:ready" in completed.stdout
    assert "make local-kubernetes-evidence-drill" in completed.stdout
    assert "make platform-toolkit-validate-cloud" in completed.stdout


def test_workload_readiness_cli_outputs_scoped_views() -> None:
    expected_headers = {
        "local": [
            "workload",
            "kind",
            "class",
            "owner",
            "use_cases",
            "local_compose",
            "local_kubernetes",
            "local_kubernetes_admission",
            "service_endpoints",
            "logs_contract",
            "metrics_contract",
            "eventing_contract",
            "idempotency_contract",
            "job_terminal_event",
            "config_contract",
            "config_env",
            "config_realization",
            "secret_injection",
            "secret_names",
            "proof_surface",
        ],
        "aws": [
            "workload",
            "kind",
            "class",
            "owner",
            "use_cases",
            "aws_ecs_supported",
            "aws_ecs_admitted",
            "policy_delivery_gate",
            "build_matrix",
            "logs_contract",
            "metrics_contract",
            "eventing_contract",
            "idempotency_contract",
            "run_workflow",
            "evidence",
            "rollback_proof",
            "log_group",
            "config_contract",
            "config_env",
            "config_realization",
            "secret_injection",
            "secret_names",
        ],
        "all": [
            "workload",
            "kind",
            "class",
            "owner",
            "use_cases",
            "local_compose",
            "local_kubernetes",
            "aws_ecs_supported",
            "aws_ecs_admitted",
            "policy_delivery_gate",
            "local_kubernetes_admission",
            "proof_surface",
            "build_matrix",
            "service_endpoints",
            "logs_contract",
            "metrics_contract",
            "eventing_contract",
            "idempotency_contract",
            "job_terminal_event",
            "run_workflow",
            "evidence",
            "rollback_proof",
            "log_group",
            "config_contract",
            "config_env",
            "config_realization",
            "secret_injection",
            "secret_names",
        ],
        "addition": [
            "workload",
            "app_files",
            "uv_workspace",
            "dockerfile_copy",
            "compose_service",
            "runtime_conformance",
            "catalog_component",
            "app_tests",
        ],
    }

    for view, header in expected_headers.items():
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/platform/workload_readiness.py",
                "--view",
                view,
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        assert completed.stdout.splitlines()[0].split("\t") == header


def test_workload_readiness_check_passes_for_current_contract() -> None:
    assert readiness_failures(readiness_rows()) == []


def test_workload_readiness_check_reports_actionable_aws_gaps() -> None:
    rows = [
        {
            "workload": "example_job",
            "kind": "job",
            "class": "operator-job",
            "owner": "platform-engineering",
            "use_cases": "operator-task",
            "local_compose": "yes",
            "local_kubernetes": "no",
            "aws_ecs_supported": "yes",
            "aws_ecs_admitted": "yes",
            "local_kubernetes_admission": "n/a",
            "proof_surface": "runtime-conformance",
            "build_matrix": "no",
            "service_endpoints": "n/a",
            "logs_contract": "missing",
            "metrics_contract": "n/a",
            "eventing_contract": "n/a",
            "idempotency_contract": "run_id",
            "job_terminal_event": "missing",
            "run_workflow": "missing",
            "evidence": "n/a",
            "rollback_proof": "missing",
            "log_group": "missing",
            "config_contract": "missing",
            "config_realization": (
                "local-compose:missing:EXAMPLE_ENV,aws-ecs:missing:EXAMPLE_ENV"
            ),
            "secret_injection": (
                "local-compose:missing:DB_PASSWORD,aws-ecs:missing:DB_PASSWORD"
            ),
        }
    ]

    failures = readiness_failures(rows)

    assert (
        "example_job: AWS-admitted workload is missing image build coverage" in failures
    )
    assert "example_job: AWS-admitted workload lacks run workflow" in failures
    assert "example_job: AWS-admitted workload lacks evidence surface" in failures
    assert "example_job: AWS-admitted workload lacks rollback proof" in failures
    assert "example_job: local workload lacks logs contract" in failures
    assert "example_job: AWS-admitted workload lacks logs contract" in failures
    assert "example_job: local Compose lacks config realization" in failures
    assert "example_job: AWS-admitted workload lacks config realization" in failures
    assert "example_job: local Compose lacks secret injection proof" in failures
    assert "example_job: AWS-admitted workload lacks secret injection proof" in failures


def test_workload_readiness_check_reports_actionable_service_gaps() -> None:
    rows = [
        {
            "workload": "example_api",
            "kind": "service",
            "class": "edge-service",
            "owner": "platform-engineering",
            "use_cases": "http-api",
            "local_compose": "yes",
            "local_kubernetes": "yes",
            "aws_ecs_supported": "yes",
            "aws_ecs_admitted": "yes",
            "local_kubernetes_admission": "ready",
            "proof_surface": "runtime-conformance,local-kubernetes-evidence-drill",
            "build_matrix": "yes",
            "service_endpoints": "missing",
            "logs_contract": "http_request:event,request_id,route,status_code",
            "metrics_contract": "missing",
            "eventing_contract": "n/a",
            "idempotency_contract": "n/a",
            "job_terminal_event": "n/a",
            "run_workflow": "app-deploy.yml",
            "evidence": "app-deploy.yml",
            "rollback_proof": "app_image",
            "log_group": "/ecs/<stack>/example-api",
            "config_contract": "declared",
            "config_realization": "local-compose,local-kubernetes,aws-ecs",
            "secret_injection": "local-compose,local-kubernetes,aws-ecs",
        }
    ]

    failures = readiness_failures(rows)

    assert "example_api: local service lacks /health, /ready, or /metrics" in failures
    assert "example_api: local service lacks metrics contract" in failures
    assert (
        "example_api: AWS-admitted service lacks /health, /ready, or /metrics"
        in failures
    )
    assert "example_api: AWS-admitted service lacks metrics contract" in failures


def test_workload_readiness_check_reports_missing_identity_fields() -> None:
    rows = [
        {
            "workload": "example_worker",
            "kind": "job",
            "class": "operator-job",
            "owner": "missing",
            "use_cases": "missing",
            "local_compose": "no",
            "local_kubernetes": "no",
            "aws_ecs_supported": "no",
            "aws_ecs_admitted": "no",
            "local_kubernetes_admission": "n/a",
            "proof_surface": "missing",
            "build_matrix": "yes",
            "service_endpoints": "n/a",
            "logs_contract": "example_worker_succeeded:event,job_name",
            "metrics_contract": "n/a",
            "eventing_contract": "n/a",
            "idempotency_contract": "run_id",
            "job_terminal_event": "missing",
            "run_workflow": "not-aws-admitted",
            "evidence": "n/a",
            "rollback_proof": "not-aws-admitted",
            "log_group": "not-aws-admitted",
            "config_contract": "missing",
            "config_realization": "none",
            "secret_injection": "none",
        }
    ]

    failures = readiness_failures(rows)

    assert "example_worker: workload lacks portable owner" in failures
    assert "example_worker: workload lacks target-neutral use cases" in failures


def test_workload_readiness_check_reports_eventing_and_idempotency_gaps() -> None:
    rows = [
        {
            "workload": "example_consumer",
            "kind": "service",
            "class": "internal-service",
            "owner": "platform-engineering",
            "use_cases": "event-consumer",
            "local_compose": "yes",
            "local_kubernetes": "no",
            "aws_ecs_supported": "yes",
            "aws_ecs_admitted": "yes",
            "local_kubernetes_admission": "n/a",
            "proof_surface": "runtime-conformance,aws-ecs-evidence",
            "build_matrix": "yes",
            "service_endpoints": "/health,/ready,/metrics",
            "logs_contract": "http_request:event,request_id,route,status_code",
            "metrics_contract": "workload_info,http_requests_total",
            "eventing_contract": "missing",
            "idempotency_contract": "n/a",
            "job_terminal_event": "n/a",
            "run_workflow": "app-deploy.yml",
            "evidence": "app-deploy.yml",
            "rollback_proof": "app_image",
            "log_group": "/ecs/<stack>/example-consumer",
            "config_contract": "declared",
            "config_realization": "local-compose,aws-ecs",
            "secret_injection": "local-compose,aws-ecs",
        },
        {
            "workload": "example_job",
            "kind": "job",
            "class": "operator-job",
            "owner": "platform-engineering",
            "use_cases": "operator-task",
            "local_compose": "yes",
            "local_kubernetes": "no",
            "aws_ecs_supported": "yes",
            "aws_ecs_admitted": "yes",
            "local_kubernetes_admission": "n/a",
            "proof_surface": "runtime-conformance,aws-ecs-evidence",
            "build_matrix": "yes",
            "service_endpoints": "n/a",
            "logs_contract": "example_job_succeeded:event,job_name",
            "metrics_contract": "n/a",
            "eventing_contract": "n/a",
            "idempotency_contract": "missing",
            "job_terminal_event": "example_job_succeeded",
            "run_workflow": "data-example.yml",
            "evidence": "data-example.yml",
            "rollback_proof": "n/a",
            "log_group": "/ecs/<stack>/example-job",
            "config_contract": "declared",
            "config_realization": "local-compose,aws-ecs",
            "secret_injection": "local-compose,aws-ecs",
        },
    ]

    failures = readiness_failures(rows)

    assert "example_consumer: local eventing contract is incomplete" in failures
    assert "example_consumer: AWS-admitted eventing contract is incomplete" in failures
    assert "example_job: local job lacks idempotency contract" in failures
    assert "example_job: AWS-admitted job lacks idempotency contract" in failures
