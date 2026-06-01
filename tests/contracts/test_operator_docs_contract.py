from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_runbooks_delegate_release_evidence_loop_to_operator_day_2() -> None:
    repeated_loop = re.compile(
        r"make release-evidence-runs\s+"
        r"GH_RUN_ID=<workflow-run-id> make release-evidence-download\s+"
        r"RELEASE_EVENTS_DIR=",
        re.MULTILINE,
    )

    for path in sorted((ROOT / "docs" / "runbooks").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        assert not repeated_loop.search(text), path


def test_runbooks_keep_runtime_inventory_resolution_in_existing_helper() -> None:
    data_export_runbook = _read("docs/runbooks/data-export-job-failure.md")

    assert "scripts/ci/resolve_ecs_task_context.py" in data_export_runbook
    assert "aws ec2 describe-subnets" not in data_export_runbook
    assert "aws ec2 describe-security-groups" not in data_export_runbook


def test_runbooks_do_not_pin_historical_workflow_run_ids() -> None:
    for path in sorted((ROOT / "docs" / "runbooks").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"`\d{8,}`", text), path


def test_deployment_delegates_evidence_commands_to_operator_day_2() -> None:
    text = _read("docs/deployment.md")

    assert "[Operator Day 2 Commands](operator-day-2.md)" in text
    assert "GH_RUN_ID=<workflow-run-id> make release-evidence-download" not in text
    assert "GH_RUN_ID=<workflow-run-id> make operator-payload-download" not in text
    assert "RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence" not in text


def test_deployment_rollout_checks_use_runtime_outputs_not_fixed_service_names() -> (
    None
):
    text = _read("docs/deployment.md")

    assert "--services api" not in text
    assert "--service-name api" not in text
    assert "${STACK_NAME:-aws-sdlc-containers}" not in text
    assert "terraform -chdir=infra/app output -raw primary_edge_service_name" in text


def test_operator_day_2_remains_short_operator_path() -> None:
    text = _read("docs/operator-day-2.md")

    assert "[Operator Day 2 Commands]" not in text
    assert "make release-evidence-runs" in text
    assert (
        "RELEASE_EVENTS_DIR=/tmp/aws-sdlc-containers-release-evidence/<workflow-run-id>"
        in text
    )
