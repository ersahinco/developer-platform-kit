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


def test_task_execution_role_can_read_parameter_backed_primary_edge_runtime_secret() -> (
    None
):
    runtime_identity = (ROOT / "infra/app/runtime_identity.tf").read_text(
        encoding="utf-8"
    )

    assert "ssm:GetParameter" in runtime_identity
    assert "ssm:GetParameters" in runtime_identity
    assert (
        "arn:aws:ssm:${local.region}:${local.account_id}:parameter/${local.primary_edge_auth_token_secret_name}"
        in runtime_identity
    )
