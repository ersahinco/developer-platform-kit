from __future__ import annotations

from pathlib import Path
import re


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
    providers = (ROOT / "infra/app/providers.tf").read_text(encoding="utf-8")
    runtime_identity = (ROOT / "infra/app/runtime_identity.tf").read_text(
        encoding="utf-8"
    )

    assert "local.primary_edge_auth_token_secret_arn" in workload_inventory
    assert "local.primary_edge_auth_token_secret_arn" in providers
    assert "primary_edge_auth_token_secret_arn_wildcard" in providers
    assert "secretsmanager:GetSecretValue" in runtime_identity
    assert "local.primary_edge_auth_token_secret_arn_wildcard" in runtime_identity
    assert "ssm:GetParameter" not in runtime_identity
    assert "ssm:GetParameters" not in runtime_identity


def test_github_actions_oidc_role_can_describe_primary_edge_runtime_secret() -> None:
    platform_identity = (ROOT / "infra/platform/github_actions.tf").read_text(
        encoding="utf-8"
    )

    assert "SecretsManagerDescribe" in platform_identity
    assert re.search(
        r"secret:\$\{local\.name\}/edge-token\*",
        platform_identity,
    )
    assert '"secretsmanager:GetResourcePolicy"' in platform_identity
