from __future__ import annotations

from scripts.ci import terraform_readiness


def test_known_provider_blockers_are_actionable() -> None:
    assert "ExpiredToken" in terraform_readiness.ACTIONABLE_BLOCKERS
    assert "Failed to query available provider packages" in (
        terraform_readiness.ACTIONABLE_BLOCKERS
    )
