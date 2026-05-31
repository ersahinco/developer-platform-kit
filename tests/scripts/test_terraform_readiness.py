from __future__ import annotations

from scripts.ci import terraform_readiness


def test_known_provider_blockers_are_actionable() -> None:
    assert "ExpiredToken" in terraform_readiness.ACTIONABLE_BLOCKERS
    assert "Failed to query available provider packages" in (
        terraform_readiness.ACTIONABLE_BLOCKERS
    )


def test_terraform_env_preserves_real_aws_credentials(monkeypatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "real-access-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "real-secret-key")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "real-session-token")

    env = terraform_readiness.terraform_env()

    assert env["AWS_ACCESS_KEY_ID"] == "real-access-key"
    assert env["AWS_SECRET_ACCESS_KEY"] == "real-secret-key"
    assert env["AWS_SESSION_TOKEN"] == "real-session-token"
    assert env["AWS_EC2_METADATA_DISABLED"] == "true"
