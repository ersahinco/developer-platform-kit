"""Export the three manifests as native Backstage Software Templates.

No custom Backstage action or running portal is required by this repository.
JSON descriptors are valid YAML and keep the CLI standard-library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from scaffold.new_repo import (
    TOKEN_PATTERN,
    TemplateError,
    available_templates,
    example_values,
    parse_set,
    resolve_values,
    template_files,
)


def skeleton(text: str) -> str:
    # Preserve GitHub's ${{ }} expressions literally through fetch:template.
    pieces = TOKEN_PATTERN.split(text)
    result = []
    for index, piece in enumerate(pieces):
        if index % 2:
            expression = f"values.{piece}"
            if piece.endswith("_SLUG"):
                expression = f'values.{piece.removesuffix("_SLUG")}_NAME | replace("-", "_")'
            result.append("${{ " + expression + " }}")
        elif piece:
            result.append("{% raw %}" + piece + "{% endraw %}")
    return "".join(result)


def export(
    output: Path,
    provider: str = "github",
    base_url: str = "https://github.com",
    allowed_owners: tuple[str, ...] = (),
    fixed_values: dict[str, str] | None = None,
    github_settings: dict | None = None,
) -> None:
    templates = available_templates()
    fixed_values = fixed_values or {}
    declared = {variable.name for template in templates for variable in template.variables}
    invalid = set(fixed_values) - (declared - {"REPOSITORY", "REPOSITORY_BASE_URL"})
    if invalid:
        raise TemplateError(f"Unknown or derived fixed variables: {', '.join(sorted(invalid))}.")
    # Validate every supplied value before creating any output. Shared values apply
    # only to templates that declare them; e.g. STATE_BUCKET belongs to infra.
    for template in templates:
        supplied = {
            variable.name: fixed_values[variable.name]
            for variable in template.variables
            if variable.name in fixed_values
        }
        resolve_values(template, example_values(template) | supplied)
    if provider not in {"github", "gitea"}:
        raise TemplateError(f"Unsupported Git provider: {provider}.")
    github_settings = {} if github_settings is None else github_settings
    validate_github_settings(github_settings)
    if github_settings and (provider != "github" or len(allowed_owners) != 1):
        raise TemplateError("GitHub settings require GitHub and exactly one --allowed-owner.")
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]+)?(?:/[A-Za-z0-9._-]+)*", base_url):
        raise TemplateError("Git base URL must be HTTPS with no credentials, query, or fragment.")
    host = urlsplit(base_url).netloc
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", owner) for owner in allowed_owners):
        raise TemplateError("Allowed owners must be Git usernames or organizations.")
    owners = "(?:" + "|".join(re.escape(owner) for owner in allowed_owners) + ")"
    owner_pattern = owners if allowed_owners else r"[A-Za-z0-9][A-Za-z0-9_.-]*"
    repo_pattern = r"[A-Za-z0-9_.-]+"
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise TemplateError(f"{output} must be an empty directory.")
    for template in templates:
        destination = output / template.name
        properties = {}
        values = {}
        required = []
        for variable in template.variables:
            if variable.name in fixed_values:
                values[variable.name] = fixed_values[variable.name]
                continue
            if variable.name == "REPOSITORY_BASE_URL":
                values[variable.name] = base_url
                continue
            if variable.name == "REPOSITORY":
                values[variable.name] = (
                    "${{ (parameters.repoUrl | parseRepoUrl).owner }}"
                    "/${{ (parameters.repoUrl | parseRepoUrl).repo }}"
                )
                continue
            properties[variable.name] = {
                "type": "string",
                "description": variable.description,
                "pattern": variable.pattern,
            }
            if variable.default is not None:
                properties[variable.name]["default"] = variable.default
            else:
                required.append(variable.name)
            values[variable.name] = "${{ parameters." + variable.name + " }}"
        properties["repoUrl"] = {
            "type": "string",
            "title": "Repository",
            # Picker options guide the UI; JSON Schema also validates direct task requests.
            "pattern": (
                rf"^{re.escape(host)}\?(?:owner={owner_pattern}&repo={repo_pattern}"
                rf"|repo={repo_pattern}&owner={owner_pattern})$"
            ),
            "ui:field": "RepoUrlPicker",
            "ui:options": {
                "allowedHosts": [host],
                **({"allowedOwners": list(allowed_owners)} if allowed_owners else {}),
            },
        }
        required.append("repoUrl")
        for source in template_files(template.files_dir):
            target = destination / "skeleton" / source.relative_to(template.files_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(skeleton(source.read_text()))
        document = {
            "apiVersion": "scaffolder.backstage.io/v1beta3",
            "kind": "Template",
            "metadata": {"name": f"platform-{template.name}", "description": template.description},
            "spec": {
                "owner": fixed_values.get("OWNER", "platform-engineering"),
                "type": template.name,
                "parameters": [
                    {"title": "New repository", "required": required, "properties": properties}
                ],
                "steps": [
                    {
                        "id": "fetch",
                        "name": "Render",
                        "action": "fetch:template",
                        "input": {"url": "./skeleton", "values": values},
                    },
                    {
                        "id": "publish",
                        "name": "Publish",
                        "action": f"publish:{provider}",
                        "input": {
                            "repoUrl": "${{ parameters.repoUrl }}",
                            "defaultBranch": "main",
                            **({"repoVisibility": "private"} if provider == "github" else {}),
                        },
                    },
                    {
                        "id": "register",
                        "name": "Register",
                        "action": "catalog:register",
                        "input": {
                            "repoContentsUrl": "${{ steps.publish.output.repoContentsUrl }}",
                            "catalogInfoPath": (
                                "catalog-info.yaml" if provider == "gitea" else "/catalog-info.yaml"
                            ),
                        },
                    },
                ],
                "output": {
                    "links": [
                        {"title": "Repository", "url": "${{ steps.publish.output.remoteUrl }}"},
                        {"title": "Catalog", "entityRef": "${{ steps.register.output.entityRef }}"},
                    ]
                },
            },
        }
        if template.name in github_settings:
            settings = github_settings[template.name]
            steps = document["spec"]["steps"]
            environments = [
                {
                    "name": "aws",
                    "deploymentBranchPolicy": {
                        "protected_branches": False,
                        "custom_branch_policies": True,
                    },
                    "customBranchPolicyNames": ["main"],
                }
            ]
            if template.name == "infra":
                # PR plans need their own limited role; they cannot use the
                # main-only apply environment. No write credential is shared.
                environments.append({"name": "aws-plan"})
            # Create settings and environments before pushing the first commit:
            # that push can immediately start the generated delivery workflow.
            steps[1:2] = [
                {
                    "id": "create",
                    "name": "Create repository and configure delivery",
                    "action": "github:repo:create",
                    "input": {
                        "repoUrl": "${{ parameters.repoUrl }}",
                        "repoVisibility": "private",
                        **settings,
                    },
                },
                *[
                    {
                        "id": f"environment-{index}",
                        "name": f"Configure {environment['name']} environment",
                        "action": "github:environment:create",
                        "input": {"repoUrl": "${{ parameters.repoUrl }}", **environment},
                    }
                    for index, environment in enumerate(environments)
                ],
                {
                    "id": "publish",
                    "name": "Push starter",
                    "action": "github:repo:push",
                    "input": {
                        "repoUrl": "${{ parameters.repoUrl }}",
                        "defaultBranch": "main",
                        "protectDefaultBranch": True,
                    },
                },
            ]
        (destination / "template.yaml").write_text(json.dumps(document, indent=2) + "\n")
    (output / "catalog-info.yaml").write_text(
        json.dumps(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Location",
                "metadata": {"name": "developer-platform-kit-templates"},
                "spec": {"targets": [f"./{t.name}/template.yaml" for t in templates]},
            },
            indent=2,
        )
        + "\n"
    )


def validate_github_settings(settings: dict) -> None:
    """Accept native action settings for current consumers, never publishing tokens."""
    templates = {template.name: template for template in available_templates()}
    if not isinstance(settings, dict) or set(settings) - templates.keys():
        raise TemplateError("GitHub settings must be an object keyed by app, infra, or data.")
    for name, entry in settings.items():
        if not isinstance(entry, dict) or set(entry) - {
            "collaborators",
            "repoVariables",
            "secrets",
        }:
            raise TemplateError(f"{name}: use native collaborators, repoVariables, or secrets.")
        workflow = "\n".join(
            path.read_text()
            for path in (templates[name].files_dir / ".github/workflows").glob("*.yml")
        )
        variables = set(re.findall(r"vars\.([A-Z_]+)", workflow))
        secrets = set(re.findall(r"secrets\.([A-Z_]+)", workflow))
        for field, names in (("repoVariables", variables), ("secrets", secrets)):
            values = entry.get(field, {})
            if not isinstance(values, dict) or set(values) - names:
                raise TemplateError(
                    f"{name}.{field}: only settings used by this starter are accepted."
                )
            for key, value in values.items():
                if not isinstance(value, str) or not value or "${{" in value or "{%" in value:
                    raise TemplateError(f"{name}.{field}.{key}: use a non-empty literal string.")
                if field == "secrets" and not re.fullmatch(
                    r"arn:aws(?:-us-gov|-cn)?:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]+", value
                ):
                    raise TemplateError(
                        f"{name}.{field}.{key}: only an existing IAM role ARN is allowed."
                    )
                if key == "PUBLISH_IMAGES" and value not in {"true", "false"}:
                    raise TemplateError(f"{name}.repoVariables.PUBLISH_IMAGES: use true or false.")
        collaborators = entry.get("collaborators", [])
        if not isinstance(collaborators, list) or any(
            not isinstance(team, dict)
            or set(team) != {"team", "access"}
            or not isinstance(team["access"], str)
            or team["access"] not in {"pull", "triage", "push", "maintain"}
            or not isinstance(team["team"], str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", team["team"])
            for team in collaborators
        ):
            raise TemplateError(
                f"{name}.collaborators: use team slugs with pull, triage, push, or maintain access."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--provider", choices=["github", "gitea"], default="github")
    parser.add_argument("--base-url", default="https://github.com")
    parser.add_argument("--allowed-owner", action="append", default=[])
    parser.add_argument(
        "--github-settings",
        type=Path,
        help="JSON file of native GitHub repository and environment settings, keyed by starter.",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="NAME=value",
        help="Fix a platform-owned template value and omit it from the developer form.",
    )
    args = parser.parse_args()
    try:
        export(
            args.output,
            args.provider,
            args.base_url,
            tuple(args.allowed_owner),
            parse_set(args.set),
            json.loads(args.github_settings.read_text()) if args.github_settings else None,
        )
    except (TemplateError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Backstage templates exported to {args.output}. Publish and register catalog-info.yaml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
