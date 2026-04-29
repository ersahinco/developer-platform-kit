from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")
EXTERNAL_SCHEMES = (
    "http://",
    "https://",
    "mailto:",
    "tel:",
)


def _tracked_markdown_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line]


def _link_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if not target:
        return None
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]

    # Drop optional Markdown link titles: [text](path "title").
    target = target.split()[0]

    if target.startswith(EXTERNAL_SCHEMES) or target.startswith("#"):
        return None

    return target.split("#", 1)[0].split("?", 1)[0]


def _resolve_link(source: Path, target: str) -> Path:
    decoded = unquote(target)
    if decoded.startswith("/"):
        return REPO_ROOT / decoded.lstrip("/")
    return (source.parent / decoded).resolve()


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def main() -> int:
    failures: list[str] = []

    for path in _tracked_markdown_files():
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = _link_target(match.group(1))
            if target is None:
                continue

            resolved = _resolve_link(path, target)
            try:
                resolved.relative_to(REPO_ROOT)
            except ValueError:
                failures.append(
                    f"{path.relative_to(REPO_ROOT)}:{_line_number(text, match.start())}: "
                    f"link escapes repo: {match.group(1)}"
                )
                continue

            if not resolved.exists():
                failures.append(
                    f"{path.relative_to(REPO_ROOT)}:{_line_number(text, match.start())}: "
                    f"missing link target: {match.group(1)}"
                )

    if failures:
        print("Broken local Markdown links:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
