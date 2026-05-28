from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/ci_guard_infra_plan_blast_radius.sh"


def _run_guard(plan: Path, *, allow: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if allow:
        env["ALLOW_ECS_TASK_DEFINITION_CHANGES"] = "allow-ecs-task-definition-changes"
    else:
        env.pop("ALLOW_ECS_TASK_DEFINITION_CHANGES", None)

    return subprocess.run(
        [str(SCRIPT), str(plan)],
        check=False,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def test_infra_plan_guard_allows_clean_plan(tmp_path: Path) -> None:
    plan = tmp_path / "plan.txt"
    plan.write_text(
        """
Terraform will perform the following actions:

  # aws_cloudwatch_metric_alarm.primary_edge_target_latency[0] will be updated in-place
  ~ resource "aws_cloudwatch_metric_alarm" "primary_edge_target_latency" {
      alarm_description = "latency alarm threshold"
    }
""",
        encoding="utf-8",
    )

    result = _run_guard(plan)

    assert result.returncode == 0
    assert result.stderr == ""


def test_infra_plan_guard_blocks_ecs_task_definition_changes(tmp_path: Path) -> None:
    plan = tmp_path / "plan.txt"
    plan.write_text(
        """
Terraform will perform the following actions:

  # module.ecs.module.service["primary-edge"].aws_ecs_task_definition.this[0] must be replaced
-/+ resource "aws_ecs_task_definition" "this" {
      family = "aws-sdlc-containers"
    }
""",
        encoding="utf-8",
    )

    result = _run_guard(plan)

    assert result.returncode == 1
    assert "Reviewed app plan contains ECS task definition changes." in result.stderr
    assert "app deploy ownership boundary" in result.stderr
    assert "aws_ecs_task_definition.this[0] must be replaced" in result.stderr


def test_infra_plan_guard_allows_ecs_task_definition_data_reads(
    tmp_path: Path,
) -> None:
    plan = tmp_path / "plan.txt"
    plan.write_text(
        """
Terraform will perform the following actions:

  # data.aws_ecs_task_definition.primary_edge_current will be read during apply
  <= data "aws_ecs_task_definition" "primary_edge_current" {
      task_definition = "aws-sdlc-containers"
    }
""",
        encoding="utf-8",
    )

    result = _run_guard(plan)

    assert result.returncode == 0
    assert result.stderr == ""


def test_infra_plan_guard_blocks_service_desired_count_changes(
    tmp_path: Path,
) -> None:
    plan = tmp_path / "plan.txt"
    plan.write_text(
        """
Terraform will perform the following actions:

  # aws_ecs_service.primary_edge will be updated in-place
  ~ resource "aws_ecs_service" "primary_edge" {
      ~ desired_count = 1 -> 0
    }
""",
        encoding="utf-8",
    )

    result = _run_guard(plan)

    assert result.returncode == 1
    assert "Reviewed app plan changes ECS service desired_count." in result.stderr
    assert "Desired rollout settings belong to app deploy" in result.stderr
    assert 'resource "aws_ecs_service" "primary_edge"' in result.stderr


def test_infra_plan_guard_allows_reviewed_override(tmp_path: Path) -> None:
    plan = tmp_path / "plan.txt"
    plan.write_text(
        """
Terraform will perform the following actions:

  # module.ecs.module.service["primary-edge"].aws_ecs_task_definition.this[0] will be created
  + resource "aws_ecs_task_definition" "this" {
      family = "aws-sdlc-containers"
    }
""",
        encoding="utf-8",
    )

    result = _run_guard(plan, allow=True)

    assert result.returncode == 0
    assert result.stderr == ""
