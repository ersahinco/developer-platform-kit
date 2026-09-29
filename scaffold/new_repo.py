"""Render repository templates using manifest values and __TOKEN__ substitution."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

TEMPLATE_ROOT = Path(__file__).resolve().parent / "repo-templates"
if not TEMPLATE_ROOT.is_dir():
    TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "repo-templates"
TOKEN_PATTERN = re.compile(r"__([A-Z][A-Z0-9_]*?)__")

CACHE_DIRS = {".ruff_cache", ".pytest_cache", "__pycache__", ".terraform", ".venv"}


def template_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and not CACHE_DIRS.intersection(path.relative_to(root).parts)
    ]


class TemplateError(Exception):
    """A problem with the template or the values given for it."""


@dataclass(frozen=True)
class Variable:
    name: str
    description: str
    example: str | None = None
    default: str | None = None
    pattern: str | None = None


@dataclass(frozen=True)
class Template:
    name: str
    description: str
    variables: tuple[Variable, ...]
    root: Path

    @property
    def files_dir(self) -> Path:
        return self.root / "files"


def load_template(name: str) -> Template:
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        raise TemplateError(f"Invalid template name: {name!r}.")
    root = TEMPLATE_ROOT / name
    manifest = root / "template.json"
    if not manifest.is_file():
        available = ", ".join(sorted(t.name for t in available_templates())) or "none"
        raise TemplateError(f"No template named {name!r}. Available templates: {available}.")

    data = json.loads(manifest.read_text())
    if not (root / "files").is_dir():
        raise TemplateError(
            f"Template {name!r} declares a manifest but has no files/ directory to render."
        )

    return Template(
        name=data["name"],
        description=data["description"],
        variables=tuple(Variable(**entry) for entry in data["variables"]),
        root=root,
    )


def available_templates() -> list[Template]:
    if not TEMPLATE_ROOT.is_dir():
        raise TemplateError(f"Template root {TEMPLATE_ROOT} is missing.")
    return [
        load_template(path.name)
        for path in sorted(TEMPLATE_ROOT.iterdir())
        if (path / "template.json").is_file()
    ]


def example_values(template: Template) -> dict[str, str]:
    """Use manifest examples, falling back to defaults, for checks and previews."""
    values: dict[str, str] = {}
    for variable in template.variables:
        value = variable.example or variable.default
        if value is None:
            raise TemplateError(
                f"{template.name}.{variable.name} has no example and no default, "
                "so the template cannot be rendered for checking."
            )
        values[variable.name] = value
    return values


def resolve_values(template: Template, provided: dict[str, str]) -> dict[str, str]:
    """Merge provided values with defaults, then validate. Derived values are computed."""
    declared = {variable.name for variable in template.variables}
    unknown = sorted(set(provided) - declared)
    if unknown:
        raise TemplateError(
            f"Template {template.name!r} declares no variable named {', '.join(unknown)}. "
            f"Declared variables: {', '.join(sorted(declared))}."
        )

    values: dict[str, str] = {}
    missing: list[Variable] = []
    for variable in template.variables:
        value = provided.get(variable.name, variable.default)
        if value is None:
            missing.append(variable)
        else:
            values[variable.name] = value

    if missing:
        lines = [
            f"  {v.name}: {v.description}" + (f" (e.g. {v.example})" if v.example else "")
            for v in missing
        ]
        raise TemplateError("These variables have no value and no default:\n" + "\n".join(lines))

    for variable in template.variables:
        if variable.pattern and not re.fullmatch(variable.pattern, values[variable.name]):
            raise TemplateError(
                f"{variable.name}={values[variable.name]!r} does not match {variable.pattern}. "
                f"{variable.description}"
            )

    # Derive slugs after validating their source names.
    for name in list(values):
        if name.endswith("_NAME"):
            values[f"{name.removesuffix('_NAME')}_SLUG"] = values[name].replace("-", "_")

    return values


def substitute(text: str, values: dict[str, str]) -> str:
    # Leave unknown tokens intact so render() can report their source file.
    return TOKEN_PATTERN.sub(lambda match: values.get(match[1], match[0]), text)


def render(
    template: Template, output: Path, values: dict[str, str], force: bool = False
) -> list[Path]:
    if output.exists() and not output.is_dir():
        raise TemplateError(f"{output} is a file, not an output directory.")
    if output.exists() and any(output.iterdir()) and not force:
        raise TemplateError(
            f"{output} already has contents. Pass --force to render into it anyway."
        )

    unresolved: dict[str, set[str]] = {}
    pending: list[tuple[Path, Path, str]] = []

    for source in template_files(template.files_dir):
        relative = source.relative_to(template.files_dir)
        target = output / substitute(str(relative), values)
        if source.is_symlink() or not target.resolve().is_relative_to(output.resolve()):
            raise TemplateError(f"Unsafe template path: {relative}.")
        path_tokens = set(TOKEN_PATTERN.findall(str(target.relative_to(output))))
        if path_tokens:
            unresolved[str(relative)] = path_tokens

        rendered = substitute(source.read_text(), values)
        leftover = set(TOKEN_PATTERN.findall(rendered))
        if leftover:
            unresolved.setdefault(str(relative), set()).update(leftover)
        pending.append((source, target, rendered))

    if unresolved:
        detail = "\n".join(
            f"  {path}: {', '.join(sorted(tokens))}" for path, tokens in sorted(unresolved.items())
        )
        raise TemplateError("Undeclared template tokens:\n" + detail)

    # Validate the whole tree before writing, including with --force.
    for source, target, rendered in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered)
        shutil.copymode(source, target)
    return [target for _, target, _ in pending]


def parse_set(pairs: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise TemplateError(f"--set expects NAME=value, got {pair!r}.")
        name, value = pair.split("=", 1)
        values[name.strip()] = value
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dpk",
        description="Create app, infrastructure, and data repositories from maintained starters.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="List available templates.")

    describe = commands.add_parser("describe", help="Show a template's variables.")
    describe.add_argument("template")

    render_command = commands.add_parser("render", help="Render a template into a directory.")
    render_command.add_argument("template")
    render_command.add_argument("output", type=Path)
    render_command.add_argument("--set", action="append", default=[], metavar="NAME=value")
    render_command.add_argument(
        "--force", action="store_true", help="Render into a non-empty directory."
    )

    examples = commands.add_parser(
        "render-examples",
        help="Render every template with its declared examples, for linting the output.",
    )
    examples.add_argument("output", type=Path)

    args = parser.parse_args(argv)

    try:
        if args.command == "list":
            for template in available_templates():
                print(f"{template.name:<14} {template.description}")
            return 0

        if args.command == "describe":
            template = load_template(args.template)
            print(f"{template.name}: {template.description}\n")
            for variable in template.variables:
                default = f" [default: {variable.default}]" if variable.default else ""
                example = f" (e.g. {variable.example})" if variable.example else ""
                print(f"  {variable.name}{default}\n      {variable.description}{example}")
            return 0

        if args.command == "render-examples":
            for template in available_templates():
                values = resolve_values(template, example_values(template))
                render(template, args.output / template.name, values, force=True)
                print(f"{template.name} -> {args.output / template.name}")
            return 0

        template = load_template(args.template)
        values = resolve_values(template, parse_set(args.set))
        written = render(template, args.output, values, force=args.force)
    except TemplateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Rendered {template.name} into {args.output} ({len(written)} files).")
    print("Next: git init, review the README, commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
