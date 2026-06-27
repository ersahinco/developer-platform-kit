from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.platform.workload_fit_check import evaluate_candidate


ROOT = Path(__file__).resolve().parents[2]
WORKLOAD_FIXTURES = ROOT / "tests" / "fixtures" / "workloads"


def _valid_candidate() -> dict[str, object]:
    return {
        "name": "payments_gateway",
        "kind": "service",
        "use_cases": ["internal-api", "connector"],
        "owner": "payments-platform",
        "runtime": {"supported": ["local-compose"], "admitted": []},
        "operational": {"class": "internal-service", "exposure": "internal"},
        "service": {"port": 8080},
        "image": {
            "repository": "payments-gateway",
            "package": "payments-gateway",
            "command": "python -m payments_gateway.main",
        },
        "metrics": {
            "format": "prometheus",
            "required_names": ["workload_info", "http_requests_total"],
        },
        "traces": {"supported": False},
        "database": {"semantics": "postgresql", "pooling": "direct"},
        "config": {
            "env": ["DATABASE_URL", "DB_HOST", "DB_PORT", "DB_USER", "DB_NAME"],
            "secrets": ["DB_PASSWORD"],
        },
    }


def test_workload_fit_check_accepts_stable_center_candidate() -> None:
    results = evaluate_candidate(_valid_candidate())

    assert {result.status for result in results} == {"ok"}
    assert "capability_profile_fit" in {result.area for result in results}


def test_workload_fit_check_accepts_dapr_pubsub_capability_intent() -> None:
    candidate = {
        **_valid_candidate(),
        "name": "order_event_consumer",
        "use_cases": ["event-consumer", "integration"],
        "dapr": {
            "app_id": "order-event-consumer",
            "scope": "pubsub",
            "pubsub_name": "async-events-pubsub",
            "topic": "orders-v1",
            "subscription_route": "/internal/events/consume",
        },
        "config": {
            "env": [
                "DATABASE_URL",
                "DB_HOST",
                "DB_PORT",
                "DB_USER",
                "DB_NAME",
                "DAPR_HTTP_ENDPOINT",
                "DAPR_PUBSUB_NAME",
                "DAPR_TOPIC",
                "DAPR_SUBSCRIPTION_ROUTE",
            ],
            "secrets": ["DB_PASSWORD"],
        },
    }

    results = evaluate_candidate(candidate)

    assert {result.status for result in results} == {"ok"}


def test_workload_fit_check_accepts_bounded_entra_and_dns_dependencies() -> None:
    candidate = {
        **_valid_candidate(),
        "config": {
            "env": [
                "DATABASE_URL",
                "DB_HOST",
                "DB_PORT",
                "DB_USER",
                "DB_NAME",
                "IDENTITY_ISSUER",
                "PARTNER_DNS_ZONE",
            ],
            "secrets": ["DB_PASSWORD", "IDENTITY_CLIENT_SECRET"],
        },
        "bounded_dependencies": [
            {
                "name": "workforce_identity",
                "kind": "identity-provider",
                "purpose": "Authenticate inbound users through Entra ID at the platform edge.",
                "direction": "inbound",
                "owner": "identity-platform",
                "config": {
                    "env": ["IDENTITY_ISSUER"],
                    "secrets": ["IDENTITY_CLIENT_SECRET"],
                },
                "evidence": ["token validation smoke check"],
            },
            {
                "name": "partner_dns",
                "kind": "dns-provider",
                "purpose": "Publish the workload hostname through an external DNS provider.",
                "direction": "outbound",
                "owner": "network-platform",
                "config": {"env": ["PARTNER_DNS_ZONE"], "secrets": []},
                "evidence": ["delegation check"],
            },
        ],
    }

    results = evaluate_candidate(candidate)

    assert {result.status for result in results} == {"ok"}


def test_workload_fit_check_rejects_bounded_dependency_provider_wiring() -> None:
    candidate = {
        **_valid_candidate(),
        "config": {
            "env": [
                "DATABASE_URL",
                "DB_HOST",
                "DB_PORT",
                "DB_USER",
                "DB_NAME",
                "IDENTITY_ISSUER",
            ],
            "secrets": ["DB_PASSWORD", "IDENTITY_CLIENT_SECRET"],
        },
        "bounded_dependencies": [
            {
                "name": "workforce_identity",
                "kind": "identity-provider",
                "purpose": "Authenticate inbound users through Entra ID.",
                "direction": "inbound",
                "owner": "identity-platform",
                "config": {
                    "env": ["IDENTITY_ISSUER"],
                    "secrets": ["IDENTITY_CLIENT_SECRET"],
                    "tenant_id": "72f988bf-86f1-41af-91ab-2d7cd011db47",
                },
                "evidence": ["token validation smoke check"],
                "client_id": "11111111-2222-3333-4444-555555555555",
                "issuer_url": "https://login.microsoftonline.com/example/v2.0",
            }
        ],
    }

    results = evaluate_candidate(candidate)
    failures = {
        result.area: result.message for result in results if result.status == "fail"
    }

    assert "bounded_dependencies" in failures
    assert "extra keys: client_id, issuer_url" in failures["bounded_dependencies"]
    assert "extra keys: tenant_id" in failures["bounded_dependencies"]
    platform_edge = next(
        result for result in results if result.area == "platform_edge_boundary"
    )
    assert platform_edge.status == "fail"
    assert "bounded_dependencies[0].client_id" in platform_edge.message
    assert "bounded_dependencies[0].issuer_url" in platform_edge.message


def test_workload_fit_check_rejects_undeclared_bounded_dependency_config() -> None:
    candidate = {
        **_valid_candidate(),
        "bounded_dependencies": [
            {
                "name": "partner_api",
                "kind": "external-api",
                "purpose": "Call a partner API through a platform-owned edge.",
                "direction": "outbound",
                "owner": "partner-platform",
                "config": {
                    "env": ["PARTNER_API_BASE_URL"],
                    "secrets": ["PARTNER_API_TOKEN"],
                },
                "evidence": ["synthetic dependency check"],
            }
        ],
    }

    results = evaluate_candidate(candidate)
    bounded = next(
        result for result in results if result.area == "bounded_dependencies"
    )

    assert bounded.status == "fail"
    assert "config.env: PARTNER_API_BASE_URL" in bounded.message
    assert "config.secrets: PARTNER_API_TOKEN" in bounded.message


def test_workload_fit_check_accepts_operator_and_scheduled_job_intent() -> None:
    base_job = {
        "kind": "job",
        "use_cases": ["operator-task"],
        "owner": "payments-platform",
        "runtime": {"supported": ["local-compose"], "admitted": []},
        "image": {
            "repository": "payments-maintenance",
            "package": "payments-maintenance",
            "command": "python -m payments_maintenance.main",
        },
        "traces": {"supported": False},
        "config": {
            "env": ["PAYMENTS_RUN_ID", "PAYMENTS_OUTPUT_DIR"],
            "secrets": [],
        },
        "job": {"idempotency": "safe to rerun for the same run id"},
    }
    operator_job = {
        **base_job,
        "name": "payments_backfill",
        "operational": {"class": "operator-job", "trigger": "manual"},
    }
    scheduled_job = {
        **base_job,
        "name": "payments_export",
        "use_cases": ["data-export", "scheduled-pipeline"],
        "operational": {"class": "scheduled-job", "trigger": "schedule"},
    }

    assert {result.status for result in evaluate_candidate(operator_job)} == {"ok"}
    assert {result.status for result in evaluate_candidate(scheduled_job)} == {"ok"}


def test_workload_fit_check_accepts_local_kubernetes_candidate(
    tmp_path: Path,
) -> None:
    candidate = {
        **_valid_candidate(),
        "runtime": {"supported": ["local-compose", "local-kubernetes"], "admitted": []},
    }
    assert {result.status for result in evaluate_candidate(candidate)} == {"ok"}

    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(candidate_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert "fit: yes" in completed.stdout
    assert "local-compose: authn=none-local" in completed.stdout
    assert "local-kubernetes: authn=none-local-with-explicit-dev-token" in (
        completed.stdout
    )
    assert "network=clusterip-services-and-probes" in completed.stdout


def test_workload_fit_check_rejects_platform_edge_wiring() -> None:
    candidate = {
        **_valid_candidate(),
        "runtime": {"supported": ["local-compose"], "admitted": ["aws-ecs"]},
        "account_id": "123456789012",
        "dns": {"fqdn": "payments.internal.example.com"},
        "iam": {"role_arn": "arn:aws:iam::123456789012:role/payments-task-role"},
        "ci": {"jenkins": "payments-main"},
        "observability": {"datadog_index": "payments-prod"},
        "database": {
            "semantics": "rds",
            "pooling": "direct",
            "host": "payments-db.cluster-abc.eu-central-1.rds.amazonaws.com",
        },
        "config": {
            "env": ["DATABASE_URL", "DD_SERVICE"],
            "secrets": ["DB_PASSWORD", "SPLUNK_TOKEN"],
        },
    }

    results = evaluate_candidate(candidate)
    failures = {
        result.area: result.message for result in results if result.status == "fail"
    }

    assert "runtime_scope" in failures
    assert "platform_edge_boundary" in failures
    assert "database_intent" in failures
    assert "observability_contract" in failures
    assert "account_id" in failures["platform_edge_boundary"]
    assert "runtime tool wiring" in failures["platform_edge_boundary"]


def test_workload_fit_check_rejects_provider_resource_vending() -> None:
    candidate = {
        **_valid_candidate(),
        "dapr": {
            "app_id": "payments-gateway",
            "scope": "pubsub",
            "pubsub_name": "async-events-pubsub",
            "topic": "payments-v1",
            "subscription_route": "/internal/events/consume",
            "sqs_queue_url": "https://sqs.eu-central-1.amazonaws.com/123456789012/payments.fifo",
            "sns_topic_arn": "arn:aws:sns:eu-central-1:123456789012:payments.fifo",
        },
        "storage": {
            "s3_bucket_name": "payments-prod-artifacts",
            "s3_bucket_arn": "arn:aws:s3:::payments-prod-artifacts",
        },
        "runtime_resources": {
            "ecs_task_definition": "payments:42",
            "eventbridge_rule_name": "payments-nightly",
            "subnet_ids": ["subnet-1234567890abcdef0"],
        },
    }

    results = evaluate_candidate(candidate)
    platform_edge = next(
        result for result in results if result.area == "platform_edge_boundary"
    )

    assert platform_edge.status == "fail"
    remove_paths = platform_edge.details["remove_from_stable_center"]
    assert "dapr.sqs_queue_url" in remove_paths
    assert "dapr.sns_topic_arn" in remove_paths
    assert "storage.s3_bucket_name" in remove_paths
    assert "storage.s3_bucket_arn" in remove_paths
    assert "runtime_resources.ecs_task_definition" in remove_paths
    assert "runtime_resources.eventbridge_rule_name" in remove_paths
    assert "runtime_resources.subnet_ids[0]" in remove_paths


def test_workload_fit_check_rejects_runtime_admission_without_support() -> None:
    candidate = {
        **_valid_candidate(),
        "runtime": {"supported": ["local-compose"], "admitted": ["aws-ecs"]},
    }

    results = evaluate_candidate(candidate)
    runtime_scope = next(result for result in results if result.area == "runtime_scope")

    assert runtime_scope.status == "fail"
    assert "runtime.admitted must be a subset of runtime.supported" in (
        runtime_scope.message
    )


def test_workload_fit_check_cli_outputs_json(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(_valid_candidate()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(candidate_path),
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    rows = json.loads(completed.stdout)
    assert rows[0]["area"] == "stable_center_fields"
    assert {row["status"] for row in rows} == {"ok"}


def test_workload_fit_check_cli_prints_next_actions_on_success(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(_valid_candidate()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(candidate_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert "fit: yes" in completed.stdout
    assert "runtime defaults:" in completed.stdout
    assert "local-compose: authn=none-local" in completed.stdout
    assert "observability=prometheus-loki-tempo-grafana" in completed.stdout
    assert "capability profile:" in completed.stdout
    assert "- requested: network_connectivity, relational_database" in (
        completed.stdout
    )
    assert "next make workload-readiness" in completed.stdout
    assert "next make platform-doctor" in completed.stdout
    assert (
        "next add to platform/workloads.json only after local proof exists"
        in completed.stdout
    )


def test_workload_fit_check_reports_missing_profile_capability(monkeypatch) -> None:
    def profile_without_database() -> dict[str, object]:
        return {
            "infra_capabilities": [
                {"capability": "network_connectivity"},
            ],
        }

    monkeypatch.setattr(
        "scripts.platform.workload_fit_check.monorepo_capability_profile",
        profile_without_database,
    )

    results = evaluate_candidate(_valid_candidate())
    profile_fit = next(
        result for result in results if result.area == "capability_profile_fit"
    )

    assert profile_fit.status == "fail"
    assert "relational_database" in profile_fit.message
    assert profile_fit.details["missing_profile_capabilities"] == [
        "relational_database"
    ]


def test_workload_fit_check_cli_groups_removals_on_failure(tmp_path: Path) -> None:
    candidate = {
        **_valid_candidate(),
        "dns": {"fqdn": "payments.internal.example.com"},
        "iam": {"role_arn": "arn:aws:iam::123456789012:role/payments-task-role"},
        "observability": {"datadog_index": "payments-prod"},
    }
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(candidate_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert completed.returncode == 1
    assert "fit: no" in completed.stdout
    assert "remove from stable center:" in completed.stdout
    assert "- dns.fqdn" in completed.stdout
    assert "- iam.role_arn" in completed.stdout
    assert "- observability.datadog_index" in completed.stdout
    assert "keep as workload contract:" in completed.stdout
    assert "- owner" in completed.stdout
    assert "- use_cases" in completed.stdout
    assert "- database semantics" in completed.stdout


def test_workload_fit_check_rejects_messy_foreign_fixture() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(WORKLOAD_FIXTURES / "foreign_internal_service_bad.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert completed.returncode == 1
    assert "fit: no" in completed.stdout
    assert "- dns.fqdn" in completed.stdout
    assert "- iam.role_arn" in completed.stdout
    assert "- observability.datadog_index" in completed.stdout
    assert "- terraform.workspace" in completed.stdout


def test_workload_fit_check_rejects_runtime_tool_choices_in_workload_metadata() -> None:
    candidate = {
        **_valid_candidate(),
        "auth": {"okta_domain": "example.okta.com"},
        "gateway": {"kong_plugin": "jwt"},
        "policy": {"opa_bundle_url": "https://policy.example.com/bundle.tar.gz"},
    }

    results = evaluate_candidate(candidate)
    failures = {
        result.area: result.message for result in results if result.status == "fail"
    }

    assert "platform_edge_boundary" in failures
    assert "auth.okta_domain" in failures["platform_edge_boundary"]
    assert "gateway.kong_plugin" in failures["platform_edge_boundary"]
    assert "policy.opa_bundle_url" in failures["platform_edge_boundary"]


def test_workload_fit_check_accepts_corrected_foreign_fixture() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(WORKLOAD_FIXTURES / "foreign_internal_service_good.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert "fit: yes" in completed.stdout
    assert "next make workload-readiness" in completed.stdout


def test_workload_fit_check_accepts_bounded_dependency_fixture() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(WORKLOAD_FIXTURES / "bounded_dependency_entra_dns_good.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert "fit: yes" in completed.stdout


def test_workload_fit_check_rejects_bounded_dependency_fixture_wiring() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/workload_fit_check.py",
            "--candidate",
            str(WORKLOAD_FIXTURES / "bounded_dependency_provider_wiring_bad.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert completed.returncode == 1
    assert "fit: no" in completed.stdout
    assert "bounded_dependencies[0].client_id" in completed.stdout
    assert "bounded_dependencies[0].issuer_url" in completed.stdout
    assert "bounded_dependencies[0].config.tenant_id" in completed.stdout
