from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_app_runtime_surfaces_do_not_read_primary_edge_secret_payloads_in_plan() -> (
    None
):
    platform_runtime_text = "\n".join(
        [
            (ROOT / "infra/app/providers.tf").read_text(encoding="utf-8"),
            (ROOT / "infra/app/edge.tf").read_text(encoding="utf-8"),
        ]
    )

    assert 'aws_secretsmanager_secret_version" "primary_edge_token"' not in (
        platform_runtime_text
    )
    assert "secret_string" not in platform_runtime_text


def test_task_execution_role_can_read_secrets_manager_backed_primary_edge_runtime_secret() -> (
    None
):
    workload_inventory = (ROOT / "infra/app/workload_inventory.tf").read_text(
        encoding="utf-8"
    )
    runtime_identity = (ROOT / "infra/app/runtime_identity.tf").read_text(
        encoding="utf-8"
    )

    assert "data.aws_secretsmanager_secret.primary_edge_auth_token.arn" in (
        workload_inventory
    )
    assert "secretsmanager:GetSecretValue" in runtime_identity
    assert "data.aws_secretsmanager_secret.primary_edge_auth_token.arn" in (
        runtime_identity
    )
    assert "ssm:GetParameter" not in runtime_identity
    assert "ssm:GetParameters" not in runtime_identity
