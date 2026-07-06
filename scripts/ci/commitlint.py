from __future__ import annotations

import re
import sys
from pathlib import Path


ALLOWED_TYPES = {
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
}
HEADER_PATTERN = re.compile(
    r"^(?P<type>[a-z]+)(\([a-z0-9_.-]+\))?!?: (?P<description>.+)$"
)


def validate_header(header: str) -> list[str]:
    if header.startswith(("Merge ", "Revert ", "fixup! ", "squash! ")):
        return []

    errors: list[str] = []
    match = HEADER_PATTERN.match(header)
    if not match:
        return [
            "commit subject must match '<type>(optional-scope): summary'",
            f"allowed types: {', '.join(sorted(ALLOWED_TYPES))}",
        ]

    commit_type = match.group("type")
    if commit_type not in ALLOWED_TYPES:
        errors.append(
            f"commit type '{commit_type}' is not allowed; use one of: "
            + ", ".join(sorted(ALLOWED_TYPES))
        )

    description = match.group("description").strip()
    if not description:
        errors.append("commit summary must not be empty")
    if description.endswith("."):
        errors.append("commit summary must not end with a period")
    if len(header) > 72:
        errors.append("commit subject must be 72 characters or fewer")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: commitlint.py <commit-message-file>", file=sys.stderr)
        return 2

    message_path = Path(sys.argv[1])
    header = message_path.read_text(encoding="utf-8").splitlines()[0].strip()
    errors = validate_header(header)
    if not errors:
        return 0

    print("Commit message failed Conventional Commit lint:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    print(f"\nsubject: {header}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
