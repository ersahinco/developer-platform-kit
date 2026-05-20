from __future__ import annotations

from pathlib import Path

from ._helpers import read_text


def _word_count(path: str) -> int:
    return len(read_text(path).split())


def test_high_frequency_docs_stay_within_token_budgets() -> None:
    budgets = {
        "README.md": 450,
        "AGENTS.md": 1050,
        "docs/README.md": 325,
        "docs/runbooks/README.md": 160,
        "apps/AGENTS.md": 180,
        "packages/AGENTS.md": 200,
        "infra/AGENTS.md": 170,
        "tests/AGENTS.md": 180,
        "db/AGENTS.md": 160,
    }

    for path, budget in budgets.items():
        assert _word_count(path) <= budget, f"{path} exceeds {budget} words"


def test_canonical_long_docs_stay_dense() -> None:
    budgets = {
        "docs/architecture.md": 850,
        "docs/platform-contract.md": 900,
        "docs/data.md": 475,
        "docs/runtime-toolkit.md": 500,
        "docs/adding-workloads.md": 425,
        "docs/ubiquitous-language.md": 475,
        "docs/observability.md": 600,
        "docs/platform-capabilities.md": 475,
        "docs/roadmaps.md": 575,
        "docs/deployment.md": 600,
        "docs/devops-toolchain.md": 375,
        "docs/local-development.md": 425,
    }

    for path, budget in budgets.items():
        assert _word_count(path) <= budget, f"{path} exceeds {budget} words"


def test_only_canonical_delivery_doc_owns_review_command_block() -> None:
    deployment_doc = read_text("docs/deployment.md")
    for path in [
        "README.md",
        "docs/README.md",
        "docs/runbooks/README.md",
    ]:
        text = read_text(path)
        assert "make release-evidence-runs" not in text
        assert "make incident-evidence" not in text
        assert "make post-deploy-verify" not in text

    for expected in [
        "make post-deploy-verify",
        "make release-evidence-runs",
        "GH_RUN_ID=<workflow-run-id> make release-evidence-download",
        "RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id>",
        "make incident-evidence",
    ]:
        assert expected in deployment_doc


def test_kiro_steering_keeps_manual_skills_only() -> None:
    steering_files = sorted(path.name for path in Path(".kiro/steering").glob("*.md"))
    assert steering_files
    assert all(name.startswith("skill-") for name in steering_files)


def test_manual_skill_files_stay_dense() -> None:
    budgets = {
        ".kiro/steering/skill-clean-architecture.md": 275,
        ".kiro/steering/skill-ddd.md": 300,
        ".kiro/steering/skill-ddia.md": 325,
        ".kiro/steering/skill-pragmatic-programmer.md": 275,
        ".kiro/steering/skill-refactoring.md": 250,
        ".kiro/steering/skill-release-it.md": 300,
    }

    for path, budget in budgets.items():
        assert _word_count(path) <= budget, f"{path} exceeds {budget} words"
