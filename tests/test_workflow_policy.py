from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_workflows import check_workflow  # noqa: E402


def write_workflow(repo: Path, name: str, content: str) -> Path:
    workflow = repo / ".github" / "workflows" / name
    workflow.parent.mkdir(parents=True)
    workflow.write_text(content, encoding="utf-8")
    return workflow


def test_workflow_policy_accepts_self_referencing_paths_and_manual_oidc_gate(tmp_path: Path) -> None:
    workflow = write_workflow(
        tmp_path,
        "infra.yml",
        """
name: Infra

on:
  workflow_dispatch:
    inputs:
      confirm_apply:
        required: true
        type: string
  pull_request:
    paths:
      - ".github/workflows/infra.yml"
      - "infra/**"

permissions:
  id-token: write

jobs:
  apply:
    if: github.event_name == 'workflow_dispatch' && inputs.confirm_apply == 'apply'
    runs-on: ubuntu-latest
    steps:
      - run: terraform apply
""".lstrip(),
    )

    assert check_workflow(workflow, tmp_path) == []


def test_workflow_policy_requires_path_filters_to_include_the_workflow(tmp_path: Path) -> None:
    workflow = write_workflow(
        tmp_path,
        "app.yml",
        """
name: App

on:
  pull_request:
    paths:
      - "apps/**"

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: make test
""".lstrip(),
    )

    failures = check_workflow(workflow, tmp_path)

    assert failures == [
        ".github/workflows/app.yml: every paths filter must include .github/workflows/app.yml"
    ]


def test_workflow_policy_requires_typed_confirmation_for_oidc_workflows(tmp_path: Path) -> None:
    workflow = write_workflow(
        tmp_path,
        "deploy.yml",
        """
name: Deploy

on:
  workflow_dispatch:

permissions:
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: aws ecs update-service
""".lstrip(),
    )

    failures = check_workflow(workflow, tmp_path)

    assert failures == [
        ".github/workflows/deploy.yml: OIDC-enabled workflows must define a required string confirm_* workflow_dispatch input"
    ]


def test_workflow_policy_requires_confirmation_gate_for_oidc_workflows(tmp_path: Path) -> None:
    workflow = write_workflow(
        tmp_path,
        "deploy.yml",
        """
name: Deploy

on:
  workflow_dispatch:
    inputs:
      confirm_deploy:
        required: true
        type: string

permissions:
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: aws ecs update-service
""".lstrip(),
    )

    failures = check_workflow(workflow, tmp_path)

    assert failures == [
        ".github/workflows/deploy.yml: OIDC-enabled workflows must gate an AWS-changing job on workflow_dispatch and confirm_*"
    ]
