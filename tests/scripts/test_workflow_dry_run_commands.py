from __future__ import annotations

from scripts.ci import workflow_dry_run_commands


def test_dry_run_commands_use_declared_workflow_dispatch_inputs() -> None:
    for workflow in workflow_dry_run_commands.dry_run_workflows():
        declared = workflow_dry_run_commands.workflow_dispatch_inputs(workflow.path)
        generated = {name for name, _value in workflow.inputs}

        assert generated <= declared


def test_dry_run_commands_cover_release_evidence_workflows() -> None:
    assert set(workflow_dry_run_commands.generated_dry_run_workflow_names()) == set(
        workflow_dry_run_commands.release_evidence_workflows()
    )


def test_non_build_dry_run_commands_use_dry_run_switch() -> None:
    for workflow in workflow_dry_run_commands.dry_run_workflows():
        generated = dict(workflow.inputs)
        declared = workflow_dry_run_commands.workflow_dispatch_inputs(workflow.path)
        if workflow.filename == "app-build.yml":
            assert generated["confirm_build"] == "dry-run"
            continue

        assert generated["dry_run"] == "true"
        assert "dry_run" in declared


def test_workflow_dispatch_inputs_use_yaml_shape(tmp_path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """
name: Example
on:
  push:
    branches: [main]
  workflow_dispatch:
    # comments and nested metadata must not become input names
    inputs:
      image_tag:
        description: immutable image tag
      dry_run:
        type: boolean
jobs:
  validate:
    runs-on: ubuntu-latest
    steps: []
""",
        encoding="utf-8",
    )

    assert workflow_dry_run_commands.workflow_dispatch_inputs(workflow) == {
        "dry_run",
        "image_tag",
    }


def test_dry_run_commands_are_non_destructive() -> None:
    commands = [
        workflow_dry_run_commands.dispatch_command(workflow)
        for workflow in workflow_dry_run_commands.dry_run_workflows()
    ]

    assert any("app-build.yml" in command for command in commands)
    assert any("operational-snapshot.yml" in command for command in commands)
    assert any(
        "app-build.yml" in command and "-f confirm_build=dry-run" in command
        for command in commands
    )
    assert not any("-f confirm_build=build" in command for command in commands)
    assert all(
        "-f dry_run=true" in command
        or ("app-build.yml" in command and "-f confirm_build=dry-run" in command)
        for command in commands
    )


def test_default_image_tag_requires_built_image_input() -> None:
    assert workflow_dry_run_commands.default_image_tag() == "sha-<built-image-commit>"


def test_validate_local_accepts_current_workflows(capsys) -> None:
    assert workflow_dry_run_commands.validate_local() == 0

    captured = capsys.readouterr()
    assert (
        "match release-evidence workflows and local workflow_dispatch inputs"
        in captured.out
    )
    assert "non-mutating guards" in captured.out


def test_dry_run_guard_errors_reject_unguarded_mutation(tmp_path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """
name: Example
on:
  workflow_dispatch:
    inputs:
      dry_run:
        type: boolean
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Register task definition
        run: aws ecs register-task-definition --cli-input-json file://task.json
""",
        encoding="utf-8",
    )

    assert workflow_dry_run_commands.dry_run_guard_errors(workflow) == [
        "workflow.yml:deploy:Register task definition mutates runtime state in dry run"
    ]


def test_dry_run_guard_errors_accept_script_dry_run_guard(tmp_path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """
name: Example
on:
  workflow_dispatch:
    inputs:
      dry_run:
        type: boolean
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Render or register
        env:
          DRY_RUN: ${{ inputs.dry_run }}
        run: |
          if [[ "$DRY_RUN" != "true" ]]; then
            aws ecs register-task-definition --cli-input-json file://task.json
          fi
""",
        encoding="utf-8",
    )

    assert workflow_dry_run_commands.dry_run_guard_errors(workflow) == []


def test_dry_run_guard_errors_reject_release_evidence_in_dry_run(tmp_path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """
name: Example
on:
  workflow_dispatch:
    inputs:
      dry_run:
        type: boolean
jobs:
  evidence:
    runs-on: ubuntu-latest
    steps:
      - name: Evidence
        run: python3 -m scripts.observability.release_event --event-type deploy
""",
        encoding="utf-8",
    )

    assert workflow_dry_run_commands.dry_run_guard_errors(workflow) == [
        "workflow.yml:evidence emits release evidence in dry run"
    ]
