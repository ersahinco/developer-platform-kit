"""Shape checks on the three reusable lanes.

Consumers call these by ref, so a broken contract here breaks every repo that
upgraded. The rules that matter are enforced, not described.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

LANES = ("reusable-app.yml", "reusable-infra.yml", "reusable-data.yml")

# Each lane's modes, and the job that must own each one.
MODE_JOBS = {
    "reusable-app.yml": {"build": "build", "deploy": "deploy"},
    "reusable-infra.yml": {"plan": "plan", "apply": "apply"},
    "reusable-data.yml": {"migrate": "migrate", "pipeline": "pipeline"},
}


def workflow_paths() -> list[Path]:
    return sorted(WORKFLOWS_DIR.glob("*.yml"))


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _triggers(path: Path) -> dict:
    # PyYAML reads the bare key `on` as True, which is why this is not "on".
    return _load(path)[True]


def _job_text(path: Path, job: str) -> str:
    return yaml.safe_dump(_load(path)["jobs"][job])


def test_there_are_exactly_three_lanes() -> None:
    found = sorted(p.name for p in WORKFLOWS_DIR.glob("reusable-*.yml"))
    assert found == sorted(LANES), (
        f"One lane per team: app, infra, data. Found {found}. Adding a fourth needs a fourth team."
    )


@pytest.mark.parametrize("path", workflow_paths(), ids=lambda p: p.name)
def test_workflow_yaml_parses(path: Path) -> None:
    assert isinstance(_load(path), dict)


@pytest.mark.parametrize("name", LANES)
def test_lane_is_callable_and_only_callable(name: str) -> None:
    triggers = _triggers(WORKFLOWS_DIR / name)
    assert "workflow_call" in triggers, f"{name} cannot be called"
    assert set(triggers) == {"workflow_call"}, (
        f"{name} has its own triggers, so it would run in this repo instead of the consumer's"
    )


@pytest.mark.parametrize("name", LANES)
def test_every_input_is_described(name: str) -> None:
    inputs = _triggers(WORKFLOWS_DIR / name)["workflow_call"]["inputs"]
    undescribed = [key for key, spec in inputs.items() if not spec.get("description")]
    assert not undescribed, f"{name} has inputs with no description: {undescribed}"


@pytest.mark.parametrize("name", LANES)
def test_credentials_arrive_as_secrets(name: str) -> None:
    call = _triggers(WORKFLOWS_DIR / name)["workflow_call"]
    for key in call["inputs"]:
        assert "role_arn" not in key and "secret" not in key, (
            f"{name} takes {key} as an input. Credentials belong in secrets."
        )
    assert "aws_role_arn" in call["secrets"], f"{name} touches AWS without declaring aws_role_arn"


@pytest.mark.parametrize("name", LANES)
def test_each_mode_has_its_own_job_gated_on_mode(name: str) -> None:
    """One file, one job per mode. Two modes never run in the same run."""
    document = _load(WORKFLOWS_DIR / name)
    assert "mode" in document[True]["workflow_call"]["inputs"], f"{name} declares no mode input"

    for mode, job in MODE_JOBS[name].items():
        assert job in document["jobs"], f"{name} has no {job} job for mode={mode}"
        condition = document["jobs"][job].get("if", "")
        assert f"inputs.mode == '{mode}'" in condition, (
            f"{name} job {job} is not gated on mode={mode}, so it could run in the wrong mode"
        )


def test_build_and_deploy_stay_separate_jobs() -> None:
    build = _job_text(WORKFLOWS_DIR / "reusable-app.yml", "build")
    deploy = _job_text(WORKFLOWS_DIR / "reusable-app.yml", "deploy")

    assert "docker build" in build
    assert "docker build" not in deploy, (
        "The deploy mode must not build. Review happens in between."
    )
    assert "update-service" in deploy
    assert "update-service" not in build, "The build mode must not deploy."


def test_plan_and_apply_stay_separate_jobs() -> None:
    plan = _job_text(WORKFLOWS_DIR / "reusable-infra.yml", "plan")
    apply = _job_text(WORKFLOWS_DIR / "reusable-infra.yml", "apply")

    assert "terraform plan" in plan
    assert "terraform apply" not in plan, "The plan mode must not apply."
    assert "terraform apply" in apply
    assert "terraform plan" not in apply, (
        "The apply mode must not plan. It applies the plan that was reviewed."
    )


def test_infra_starter_separates_plan_and_apply_identity() -> None:
    workflow = _load(Path("repo-templates/infra/files/.github/workflows/infra.yml"))
    plan, apply = workflow["jobs"]["plan"], workflow["jobs"]["apply"]
    assert plan["with"]["environment"] == "aws-plan"
    assert apply["with"]["environment"] == "aws"
    assert plan["secrets"]["aws_role_arn"] == "${{ secrets.AWS_PLAN_ROLE_ARN }}"
    assert apply["secrets"]["aws_role_arn"] == "${{ secrets.AWS_ROLE_ARN }}"


def test_apply_verifies_the_plan_run_before_applying() -> None:
    apply = _job_text(WORKFLOWS_DIR / "reusable-infra.yml", "apply")
    for guard in ("conclusion", "head_branch", "head_sha"):
        assert guard in apply, (
            f"The apply mode does not check {guard}, so it would accept an unreviewed or stale plan"
        )


@pytest.mark.parametrize("name", LANES)
def test_cloud_changing_lane_writes_evidence(name: str) -> None:
    assert "release-event.json" in (WORKFLOWS_DIR / name).read_text(), (
        f"{name} changes a cloud account without leaving evidence"
    )


@pytest.mark.parametrize("path", workflow_paths(), ids=lambda p: p.name)
def test_actions_are_pinned_by_sha(path: Path) -> None:
    unpinned: list[str] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith(("- uses:", "uses:")):
            continue
        reference = stripped.split("uses:", 1)[1].split("#", 1)[0].strip()
        if reference.startswith(("./", "__")):
            continue
        _, _, version = reference.partition("@")
        if not re.fullmatch(r"[0-9a-f]{40}", version):
            unpinned.append(reference)
    assert not unpinned, f"{path.name} uses actions not pinned to a full SHA: {unpinned}"


def test_toolkit_workflows_never_deploy_the_old_application() -> None:
    assert {path.name for path in workflow_paths()} == {"ci.yml", *LANES}


def test_pr_build_does_not_require_cloud_credentials() -> None:
    workflow = _load(WORKFLOWS_DIR / "reusable-app.yml")
    assert not workflow[True]["workflow_call"]["secrets"]["aws_role_arn"]["required"]
    for step in workflow["jobs"]["build"]["steps"]:
        if step.get("uses", "").startswith("aws-actions/"):
            assert step["if"] == "inputs.push"


def test_consumers_grant_permissions_required_by_lanes() -> None:
    for path in (REPO_ROOT / "repo-templates").glob("*/files/.github/workflows/*.yml"):
        permissions = _load(path)["permissions"]
        assert permissions["id-token"] == "write"
        for job in _load(path)["jobs"].values():
            if "uses" in job:
                assert "secrets" in job


def test_migration_selects_published_image_before_running() -> None:
    migrate = _job_text(WORKFLOWS_DIR / "reusable-data.yml", "migrate")
    assert "imageTag=" in migrate
    assert "register-task-definition" in migrate
    assert "--count=1" in migrate


def test_spark_ships_python_package_and_check_definition() -> None:
    pipeline = _job_text(WORKFLOWS_DIR / "reusable-data.yml", "pipeline")
    assert "--py-files" in pipeline and "--files" in pipeline
    assert "GITHUB_RUN_ATTEMPT" in pipeline
