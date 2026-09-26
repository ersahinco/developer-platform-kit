"""Export the three manifests as native Backstage Software Templates.

No custom Backstage action or running portal is required by this repository.
JSON descriptors are valid YAML and keep the CLI standard-library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scaffold.new_repo import TOKEN_PATTERN, TemplateError, available_templates, template_files


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


def export(output: Path) -> None:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise TemplateError(f"{output} must be an empty directory.")
    for template in available_templates():
        destination = output / template.name
        properties = {}
        values = {}
        required = []
        for variable in template.variables:
            if variable.name == "GITHUB_REPOSITORY":
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
            "ui:field": "RepoUrlPicker",
            "ui:options": {"allowedHosts": ["github.com"]},
        }
        required.append("repoUrl")
        for source in template_files(template.files_dir):
            if not source.is_file():
                continue
            target = destination / "skeleton" / source.relative_to(template.files_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(skeleton(source.read_text()))
        document = {
            "apiVersion": "scaffolder.backstage.io/v1beta3",
            "kind": "Template",
            "metadata": {"name": f"platform-{template.name}", "description": template.description},
            "spec": {
                "owner": "platform-engineering",
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
                        "action": "publish:github",
                        "input": {
                            "repoUrl": "${{ parameters.repoUrl }}",
                            "defaultBranch": "main",
                            "repoVisibility": "private",
                        },
                    },
                    {
                        "id": "register",
                        "name": "Register",
                        "action": "catalog:register",
                        "input": {
                            "repoContentsUrl": "${{ steps.publish.output.repoContentsUrl }}",
                            "catalogInfoPath": "/catalog-info.yaml",
                        },
                    },
                ],
                "output": {
                    "links": [
                        {"title": "Repository", "url": "${{ steps.publish.output.remoteUrl }}"}
                    ]
                },
            },
        }
        (destination / "template.yaml").write_text(json.dumps(document, indent=2) + "\n")
    (output / "catalog-info.yaml").write_text(
        json.dumps(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Location",
                "metadata": {"name": "developer-platform-kit-templates"},
                "spec": {"targets": [f"./{t.name}/template.yaml" for t in available_templates()]},
            },
            indent=2,
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        export(args.output)
    except TemplateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Backstage templates exported to {args.output}. Publish and register catalog-info.yaml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
