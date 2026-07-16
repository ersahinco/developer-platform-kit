from __future__ import annotations

import re

import yaml

from ._helpers import ROOT, load_json, read_text


HYBRID_ROOTS = [
    "infra/hybrid-reference/data",
    "infra/hybrid-reference/compute",
    "infra/hybrid-reference/dns",
]
DIGEST_REF = re.compile(r"^[^\s]+@sha256:[0-9a-f]{64}$")


def test_hybrid_reference_keeps_lifecycles_and_secrets_separate() -> None:
    for root in HYBRID_ROOTS:
        versions = read_text(f"{root}/versions.tf")
        assert 'backend "s3"' in versions
        assert "use_lockfile = true" in versions
        assert "encrypt      = true" in versions
        assert "terraform_remote_state" not in "\n".join(
            path.read_text(encoding="utf-8") for path in (ROOT / root).glob("*.tf")
        )

    for path in (ROOT / "infra/hybrid-reference").glob("*/outputs.tf"):
        outputs = path.read_text(encoding="utf-8").lower()
        assert "password" not in outputs
        assert "access_key" not in outputs
        assert "database_url" not in outputs

    cloud_init = read_text("infra/hybrid-reference/compute/cloud-init.yaml.tftpl")
    for secret_name in [
        "DATABASE_URL",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "DATA_EXPORT_AWS_ACCESS_KEY_ID",
        "DATA_EXPORT_AWS_SECRET_ACCESS_KEY",
        "PRIMARY_EDGE_AUTH_TOKEN",
        "REGISTRY_PASSWORD",
    ]:
        assert secret_name not in cloud_init

    data_root = read_text("infra/hybrid-reference/data/main.tf")
    assert "ignore_changes = [database_password]" in data_root
    assert 'resource "aws_iam_user"' not in data_root
    assert 'resource "aws_iam_group_policy"' in data_root
    assert 'resource "aws_iam_group_membership"' in data_root
    assert 'resource "aws_iam_user_group_membership"' not in data_root
    assert "force_destroy = var.export_bucket_force_destroy" in data_root


def test_hybrid_runtime_uses_digest_pins_and_canonical_dapr_components() -> None:
    compose_text = read_text("infra/hybrid-reference/compute/runtime/compose.yaml")
    compose = yaml.safe_load(compose_text)

    assert compose["x-pooled-database-env"]["DATABASE_URL"].startswith(
        "${POOLED_DATABASE_URL:"
    )
    assert compose["x-direct-database-env"]["DATABASE_URL"].startswith(
        "${DIRECT_DATABASE_URL:"
    )
    assert compose["services"]["api"]["environment"]["DATABASE_URL"].startswith(
        "${POOLED_DATABASE_URL:"
    )
    assert compose["services"]["event-consumer"]["environment"][
        "DATABASE_URL"
    ].startswith("${DIRECT_DATABASE_URL:")

    for service_name in ["caddy", "booking-api-dapr", "redis", "event-consumer-dapr"]:
        assert DIGEST_REF.fullmatch(compose["services"][service_name]["image"])
    for service_name in [
        "api",
        "booking-api",
        "event-consumer",
        "data-export",
        "liquibase",
    ]:
        assert "_IMAGE:?" in compose["services"][service_name]["image"]

    operator = read_text("scripts/platform/hybrid_reference.sh")
    assert "platform/concerns/dapr/profiles/local" in operator
    assert "@sha256:<64 lowercase hex characters>" in operator
    assert "REGISTRY_PASSWORD" in operator
    assert "cloud-init" in operator


def test_hybrid_reference_realizes_provider_free_workloads() -> None:
    workloads = load_json("platform/workloads.json")["workloads"]
    support = load_json("platform/workload-runtime-support.json")
    hybrid_names = set(support["targets"]["hetzner-compose"]["supported_workloads"])

    assert hybrid_names == {"api", "booking_api", "event_consumer", "data_export_job"}
    for workload in workloads:
        assert "runtime" not in workload

    compose = read_text("infra/hybrid-reference/compute/runtime/compose.yaml")
    assert "${API_IMAGE" in compose
    assert "${BOOKING_API_IMAGE" in compose
    assert "${EVENT_CONSUMER_IMAGE" in compose
    assert "${DATA_EXPORT_IMAGE" in compose

    aws_deploy = read_text(".github/workflows/app-deploy.yml")
    assert "imageDetails[0].imageDigest" in aws_deploy
    assert '--image-digest "${{ needs.deploy.outputs.image_digest }}"' in aws_deploy


def test_hybrid_operator_path_proves_delivery_and_bounded_failure_modes() -> None:
    makefile = read_text("Makefile")
    operator = read_text("scripts/platform/hybrid_reference.sh")

    for target in [
        "hybrid-reference-prerequisites",
        "hybrid-reference-plan",
        "hybrid-reference-apply",
        "hybrid-reference-verify-origin",
        "hybrid-reference-verify",
        "hybrid-reference-evidence",
        "hybrid-reference-rollback",
        "hybrid-reference-destroy",
        "hybrid-reference-drill-database-unavailable",
        "hybrid-reference-drill-invalid-s3",
    ]:
        assert re.search(rf"^{target}:", makefile, re.MULTILINE)

    for evidence in [
        "dig +short A",
        "workload_info",
        '"workload": "api"',
        "v1.0/invoke/booking-api/method/ready",
        "v1.0/publish/async-events-pubsub",
        "duplicate_count",
        "data_export_succeeded",
        "raw_sha256",
    ]:
        assert evidence in operator

    assert makefile.index("$(HYBRID_DNS_ROOT) destroy") < makefile.index(
        "$(HYBRID_COMPUTE_ROOT) destroy"
    )
    assert makefile.index("$(HYBRID_COMPUTE_ROOT) destroy") < makefile.index(
        "$(HYBRID_DATA_ROOT) destroy"
    )


def test_hybrid_dns_retains_provider_compatible_origin_tls() -> None:
    dns = read_text("infra/hybrid-reference/dns/main.tf")
    caddy = read_text("infra/hybrid-reference/compute/runtime/Caddyfile")

    assert "proxied = false" in dns
    assert "{$HYBRID_HOSTNAME}" in caddy
    assert "reverse_proxy api:8000" in caddy


def test_hybrid_operator_surface_is_frozen_without_a_control_plane() -> None:
    operator = read_text("scripts/platform/hybrid_reference.sh")
    makefile = read_text("Makefile")
    compose = read_text("infra/hybrid-reference/compute/runtime/compose.yaml")
    cloud_init = read_text("infra/hybrid-reference/compute/cloud-init.yaml.tftpl")
    compute_main = read_text("infra/hybrid-reference/compute/main.tf")
    compute_variables = read_text("infra/hybrid-reference/compute/variables.tf")

    action_case = operator.split('case "$action" in', maxsplit=1)[1]
    actions = set(re.findall(r"^\s{2}([a-z0-9-]+)\)", action_case, re.MULTILINE))
    assert actions == {
        "prerequisites",
        "deploy",
        "migrate",
        "verify-origin",
        "verify-public",
        "export",
        "drill-database-unavailable",
        "drill-invalid-s3",
    }
    assert "show_logs" not in operator

    make_targets = set(
        re.findall(r"^(hybrid-reference-[a-z0-9-]+):", makefile, re.MULTILINE)
    )
    assert make_targets == {
        "hybrid-reference-apply",
        "hybrid-reference-compute-apply",
        "hybrid-reference-compute-init",
        "hybrid-reference-compute-plan",
        "hybrid-reference-data-apply",
        "hybrid-reference-data-init",
        "hybrid-reference-data-plan",
        "hybrid-reference-deploy",
        "hybrid-reference-destroy",
        "hybrid-reference-dns-apply",
        "hybrid-reference-dns-init",
        "hybrid-reference-dns-plan",
        "hybrid-reference-dns-rollback-apply",
        "hybrid-reference-dns-rollback-plan",
        "hybrid-reference-drill-database-unavailable",
        "hybrid-reference-drill-invalid-s3",
        "hybrid-reference-evidence",
        "hybrid-reference-export",
        "hybrid-reference-migrate",
        "hybrid-reference-plan",
        "hybrid-reference-prerequisites",
        "hybrid-reference-rollback",
        "hybrid-reference-verify",
        "hybrid-reference-verify-origin",
        "hybrid-reference-vm-replacement",
        "hybrid-reference-vm-replacement-plan",
    }

    hybrid_makefile = makefile.split("# ── Hybrid starter reference", maxsplit=1)[
        1
    ].split("# ── App — deploy", maxsplit=1)[0]
    direct_runtime = "\n".join(
        [
            operator,
            hybrid_makefile,
            compose,
            cloud_init,
            compute_main,
            compute_variables,
        ]
    ).lower()
    for product in [
        "coolify",
        "portainer",
        "kamal",
        "dokku",
        "dokploy",
        "caprover",
    ]:
        assert product not in direct_runtime

    decision = read_text("docs/adr/0003-retain-direct-hetzner-compose-reference.md")
    normalized_decision = " ".join(decision.split())
    assert "Accepted on 2026-07-16" in decision
    assert "Freeze its operator surface" in decision
    assert "must not leave a parallel product path" in normalized_decision
