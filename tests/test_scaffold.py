"""Every template must render, and the rendered output must be valid.

These tests are the only thing standing between a broken template and a team
discovering it while starting a new repo.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scaffold.new_repo import (
    TOKEN_PATTERN,
    TemplateError,
    available_templates,
    example_values,
    load_template,
    render,
    resolve_values,
)


def template_names() -> list[str]:
    return [template.name for template in available_templates()]


def _render(name: str, destination: Path) -> list[Path]:
    template = load_template(name)
    return render(template, destination, resolve_values(template, example_values(template)))


def test_there_is_one_template_per_team() -> None:
    assert set(template_names()) == {"app", "infra", "data"}, (
        "One template per team: app, infra, data. A fourth needs a fourth audience."
    )


@pytest.mark.parametrize("name", template_names())
def test_every_declared_variable_has_a_usable_value(name: str) -> None:
    template = load_template(name)
    for variable in template.variables:
        assert variable.description, f"{name}.{variable.name} has no description"
        assert variable.example or variable.default, (
            f"{name}.{variable.name} has neither an example nor a default, so nobody can guess it"
        )


@pytest.mark.parametrize("name", template_names())
def test_template_renders_with_example_values(name: str, tmp_path: Path) -> None:
    written = _render(name, tmp_path / name)

    assert written, f"{name} rendered no files"
    for path in written:
        assert path.is_file()
        assert not TOKEN_PATTERN.search(path.name), f"{path} kept an unrendered token in its name"


@pytest.mark.parametrize("name", template_names())
def test_rendered_yaml_and_json_parse(name: str, tmp_path: Path) -> None:
    for path in _render(name, tmp_path / name):
        if path.suffix in {".yml", ".yaml"}:
            yaml.safe_load(path.read_text())
        elif path.suffix == ".json":
            json.loads(path.read_text())


@pytest.mark.parametrize("name", template_names())
@pytest.mark.parametrize("owner", ["123", "null"])
def test_catalog_owner_remains_a_string(name: str, owner: str, tmp_path: Path) -> None:
    template = load_template(name)
    values = example_values(template) | {"OWNER": owner}
    render(template, tmp_path, resolve_values(template, values))
    catalog = yaml.safe_load((tmp_path / "catalog-info.yaml").read_text())
    assert catalog["spec"]["owner"] == owner


@pytest.mark.parametrize("name", template_names())
def test_rendered_python_compiles(name: str, tmp_path: Path) -> None:
    for path in _render(name, tmp_path / name):
        if path.suffix == ".py":
            compile(path.read_text(), str(path), "exec")


@pytest.mark.parametrize("workload", ["api", "platform-demo-app-20260927", "a" * 40])
def test_app_formatting_handles_supported_name_lengths(workload: str, tmp_path: Path) -> None:
    template = load_template("app")
    values = example_values(template) | {"WORKLOAD_NAME": workload}
    render(template, tmp_path, resolve_values(template, values))
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("name", template_names())
def test_rendered_dockerfiles_have_no_tokens_left(name: str, tmp_path: Path) -> None:
    """hadolint cannot read a template, so the rendered file is what gets linted.

    This test is the cheap half of that: no token survives into a Dockerfile.
    `make lint-dockerfiles` runs hadolint over the same rendered output.
    """
    for path in _render(name, tmp_path / name):
        if path.name == "Dockerfile":
            leftover = TOKEN_PATTERN.findall(path.read_text())
            assert not leftover, f"{path} still contains {leftover}"


def test_missing_value_names_the_variable() -> None:
    template = load_template("app")
    with pytest.raises(TemplateError, match="WORKLOAD_NAME"):
        resolve_values(template, {})


def test_unknown_variable_is_a_different_error_than_a_missing_one() -> None:
    template = load_template("app")
    values = example_values(template) | {"NOT_A_VARIABLE": "x"}
    with pytest.raises(TemplateError, match="declares no variable named NOT_A_VARIABLE"):
        resolve_values(template, values)


def test_pattern_violation_explains_the_rule() -> None:
    template = load_template("app")
    values = example_values(template) | {"WORKLOAD_NAME": "Orders_API"}
    with pytest.raises(TemplateError, match="does not match"):
        resolve_values(template, values)


def test_any_name_variable_gets_a_derived_slug() -> None:
    app_template = load_template("app")
    app = resolve_values(app_template, example_values(app_template))
    assert app["WORKLOAD_SLUG"] == "orders_api"

    data_template = load_template("data")
    data = resolve_values(data_template, example_values(data_template))
    assert data["PIPELINE_SLUG"] == "orders_daily"
    assert not any(v.name.endswith("_SLUG") for v in data_template.variables), (
        "A slug is derived from its name. Declaring it invites the two to disagree."
    )


def test_render_refuses_a_non_empty_directory(tmp_path: Path) -> None:
    template = load_template("app")
    values = resolve_values(template, example_values(template))
    output = tmp_path / "existing"
    output.mkdir()
    (output / "keep.txt").write_text("mine")

    with pytest.raises(TemplateError, match="already has contents"):
        render(template, output, values)

    render(template, output, values, force=True)
    assert (output / "keep.txt").read_text() == "mine"


def test_token_followed_by_underscore() -> None:
    from scaffold.new_repo import substitute

    assert (
        substitute("__WORKLOAD_SLUG___requests", {"WORKLOAD_SLUG": "orders_api"})
        == "orders_api_requests"
    )


@pytest.mark.parametrize("name", ["../app", "/tmp/app", "app/../../infra"])
def test_template_name_cannot_escape_root(name: str) -> None:
    with pytest.raises(TemplateError, match="Invalid template name"):
        load_template(name)


@pytest.mark.parametrize("in_path", [False, True])
def test_unknown_tokens_fail_before_writing(tmp_path: Path, in_path: bool) -> None:
    from dataclasses import replace

    root = tmp_path / "template"
    files = root / "files"
    files.mkdir(parents=True)
    (files / "a.txt").write_text("valid file")
    (files / ("__MISSING__" if in_path else "z.txt")).write_text("ok" if in_path else "__MISSING__")
    template = replace(load_template("app"), root=root)
    output = tmp_path / "out"
    with pytest.raises(TemplateError, match="MISSING"):
        render(template, output, {})
    assert not output.exists()


def test_force_cannot_follow_output_symlink(tmp_path: Path) -> None:
    from dataclasses import replace

    root = tmp_path / "template"
    (root / "files").mkdir(parents=True)
    (root / "files" / "file.txt").write_text("replacement")
    outside = tmp_path / "outside.txt"
    outside.write_text("keep")
    output = tmp_path / "out"
    output.mkdir()
    (output / "file.txt").symlink_to(outside)
    with pytest.raises(TemplateError, match="Unsafe template path"):
        render(replace(load_template("app"), root=root), output, {}, force=True)
    assert outside.read_text() == "keep"


@pytest.mark.parametrize("name", template_names())
def test_every_variable_has_a_pattern(name: str) -> None:
    assert all(variable.pattern for variable in load_template(name).variables)


@pytest.mark.parametrize(
    ("provider", "base_url"),
    [
        ("github", "https://github.com"),
        ("github", "https://github.example.com"),
        ("gitea", "https://cnoe.localtest.me:8443/gitea"),
    ],
)
def test_backstage_export_uses_native_actions_and_all_three_templates(
    tmp_path: Path, provider: str, base_url: str
) -> None:
    from scaffold.backstage import export

    export(tmp_path, provider, base_url)
    location = json.loads((tmp_path / "catalog-info.yaml").read_text())
    assert len(location["spec"]["targets"]) == 3
    for target in location["spec"]["targets"]:
        descriptor = tmp_path / target
        document = json.loads(descriptor.read_text())
        assert [step["action"] for step in document["spec"]["steps"]] == [
            "fetch:template",
            f"publish:{provider}",
            "catalog:register",
        ]
        values = document["spec"]["steps"][0]["input"]["values"]
        assert document["spec"]["steps"][2]["input"]["catalogInfoPath"] == (
            "catalog-info.yaml" if provider == "gitea" else "/catalog-info.yaml"
        )
        assert values["REPOSITORY_BASE_URL"] == base_url
        assert "parseRepoUrl" in values["REPOSITORY"]
        properties = document["spec"]["parameters"][0]["properties"]
        assert "REPOSITORY" not in properties
        assert "REPOSITORY_BASE_URL" not in properties
        assert (descriptor.parent / "skeleton" / "catalog-info.yaml").is_file()
        for source in (descriptor.parent / "skeleton").rglob("*"):
            if source.is_file():
                assert not TOKEN_PATTERN.search(source.read_text())


@pytest.mark.parametrize(
    "base_url",
    [
        "http://git.local",
        "https://user:pass@git.local",
        "https://git.local?x=1",
        "https://git.local/#x",
    ],
)
def test_backstage_rejects_unsafe_base_url(tmp_path: Path, base_url: str) -> None:
    from scaffold.backstage import export

    with pytest.raises(TemplateError, match="Git base URL"):
        export(tmp_path / "export", "gitea", base_url)
    assert not (tmp_path / "export").exists()


def test_backstage_destination_schema_rejects_unapproved_owners_and_hosts(tmp_path: Path) -> None:
    from scaffold.backstage import export

    export(tmp_path, allowed_owners=("platform-team",))
    document = json.loads((tmp_path / "app/template.yaml").read_text())
    repo = document["spec"]["parameters"][0]["properties"]["repoUrl"]
    assert repo["ui:options"]["allowedOwners"] == ["platform-team"]
    for value in (
        "github.com?owner=platform-team&repo=orders",
        "github.com?repo=orders&owner=platform-team",
    ):
        assert re.fullmatch(repo["pattern"], value)
    for value in (
        "evil.example?owner=platform-team&repo=orders",
        "github.com?owner=someone-else&repo=orders",
        "github.com?owner=platform-team&repo=orders&owner=someone-else",
        "github.com?owner=platform-team&repo=orders#fragment",
        "github.com?owner=platform-team&repo=../../orders",
    ):
        assert not re.fullmatch(repo["pattern"], value)


def test_backstage_platform_values_are_fixed_outside_the_form(tmp_path: Path) -> None:
    from scaffold.backstage import export

    fixed = {
        "OWNER": "team-payments",
        "AWS_REGION": "eu-west-1",
        "TOOLKIT_REPOSITORY": "acme/developer-platform-kit",
        "TOOLKIT_REF": "a" * 40,
        "STATE_BUCKET": "acme-state",
    }
    export(tmp_path, fixed_values=fixed)
    for template in available_templates():
        document = json.loads((tmp_path / template.name / "template.yaml").read_text())
        form = document["spec"]["parameters"][0]
        values = document["spec"]["steps"][0]["input"]["values"]
        declared = {variable.name for variable in template.variables}
        for name, value in fixed.items():
            assert name not in form["properties"]
            assert name not in form["required"]
            if name in declared:
                # A task request cannot override the value with its own parameters.
                assert values[name] == value
            else:
                assert name not in values
        assert "repoUrl" in form["required"]


def test_github_settings_are_applied_before_the_initial_push(tmp_path: Path) -> None:
    from scaffold.backstage import export

    settings = json.loads((Path(__file__).parent / "fixtures/github-settings.json").read_text())
    export(tmp_path, allowed_owners=("acme",), github_settings=settings)
    for name, expected in settings.items():
        document = json.loads((tmp_path / name / "template.yaml").read_text())
        steps = document["spec"]["steps"]
        actions = [step["action"] for step in steps]
        assert actions[:2] == ["fetch:template", "github:repo:create"]
        assert actions[-2:] == ["github:repo:push", "catalog:register"]
        assert set(actions[2:-2]) == {"github:environment:create"}
        for key, value in expected.items():
            assert steps[1]["input"][key] == value
        assert steps[1]["input"]["repoVisibility"] == "private"
        assert steps[2]["input"]["name"] == "aws"
        assert steps[2]["input"]["customBranchPolicyNames"] == ["main"]
        assert steps[2]["input"]["deploymentBranchPolicy"] == {
            "protected_branches": False,
            "custom_branch_policies": True,
        }
        if name == "infra":
            assert steps[3]["input"]["name"] == "aws-plan"
        assert (
            steps[-1]["input"]["repoContentsUrl"] == "${{ steps.publish.output.repoContentsUrl }}"
        )


@pytest.mark.parametrize(
    "settings",
    [
        [],
        {"unknown": {}},
        {"app": {"token": "must-not-be-exported"}},
        {"app": {"secrets": {"AWS_ROLE_ARN": "an-access-key"}}},
        {"app": {"secrets": {"AWS_SECRET_ACCESS_KEY": "must-not-be-exported"}}},
        {"app": {"repoVariables": {"UNUSED": "value"}}},
        {"app": {"repoVariables": {"ECS_CLUSTER": "${{ parameters.target }}"}}},
        {"app": {"repoVariables": {"PUBLISH_IMAGES": "yes"}}},
        {"app": {"collaborators": [{"team": "payments", "access": "admin"}]}},
        {"app": {"collaborators": [{"user": "alice", "access": "push"}]}},
    ],
)
def test_github_settings_reject_credentials_and_unconsumed_configuration(
    tmp_path: Path, settings: dict
) -> None:
    from scaffold.backstage import export

    output = tmp_path / "export"
    with pytest.raises(TemplateError):
        export(output, allowed_owners=("acme",), github_settings=settings)
    assert not output.exists()


@pytest.mark.parametrize(
    "provider,owners", [("gitea", ("acme",)), ("github", ()), ("github", ("a", "b"))]
)
def test_github_settings_require_one_organization(
    tmp_path: Path, provider: str, owners: tuple[str, ...]
) -> None:
    from scaffold.backstage import export

    with pytest.raises(TemplateError, match="exactly one"):
        export(
            tmp_path / "export",
            provider=provider,
            allowed_owners=owners,
            github_settings={"app": {}},
        )


@pytest.mark.parametrize(
    "fixed",
    [
        {"TOOLKIT_REF": "main"},
        {"STATE_BUCKET": "not a bucket"},
        {"UNDECLARED": "value"},
        {"WORKLOAD_SLUG": "derived"},
        {"REPOSITORY": "acme/override"},
        {"REPOSITORY_BASE_URL": "https://other.example"},
    ],
)
def test_backstage_rejects_invalid_fixed_values_before_writing(
    tmp_path: Path, fixed: dict[str, str]
) -> None:
    from scaffold.backstage import export

    output = tmp_path / "export"
    with pytest.raises(TemplateError):
        export(output, fixed_values=fixed)
    assert not output.exists()


@pytest.mark.parametrize("name", template_names())
def test_catalog_source_location_matches_git_host(name: str, tmp_path: Path) -> None:
    template = load_template(name)
    values = example_values(template) | {
        "REPOSITORY_BASE_URL": "https://cnoe.localtest.me:8443/gitea",
        "REPOSITORY": "platform/example",
    }
    render(template, tmp_path, resolve_values(template, values))
    catalog = yaml.safe_load((tmp_path / "catalog-info.yaml").read_text())
    assert catalog["metadata"]["annotations"]["backstage.io/source-location"] == (
        "url:https://cnoe.localtest.me:8443/gitea/platform/example"
    )
