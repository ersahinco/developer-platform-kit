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
