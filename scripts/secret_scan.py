from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


SKIPPED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".terraform",
    ".venv",
    "__pycache__",
    "node_modules",
}

SKIPPED_SUFFIXES = {
    ".7z",
    ".avif",
    ".bin",
    ".bmp",
    ".class",
    ".db",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".tar",
    ".webp",
    ".zip",
}

PLACEHOLDER_MARKERS = (
    "CHANGEME",
    "DUMMY",
    "EXAMPLE",
    "FAKE",
    "PLACEHOLDER",
    "REPLACE",
    "TEST",
)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class Finding:
    path: Path
    line_number: int
    rule_id: str
    secret: str


RULES = (
    Rule(
        rule_id="aws-access-key-id",
        pattern=re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA)[A-Z0-9]{16}\b"),
    ),
    Rule(
        rule_id="github-token",
        pattern=re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,255}\b"),
    ),
    Rule(
        rule_id="google-api-key",
        pattern=re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ),
    Rule(
        rule_id="slack-token",
        pattern=re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ),
    Rule(
        rule_id="stripe-live-secret-key",
        pattern=re.compile(r"\bsk_live_[A-Za-z0-9]{24,}\b"),
    ),
    Rule(
        rule_id="private-key",
        pattern=re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    ),
)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan text files for high-confidence committed secrets.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to scan. Defaults to the repository root.",
    )
    return parser.parse_args(argv)


def iter_candidate_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file():
            if should_scan_file(path):
                yield path
            continue

        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [dirname for dirname in dirnames if dirname not in SKIPPED_DIRS]
            directory = Path(dirpath)
            for filename in filenames:
                candidate = directory / filename
                if should_scan_file(candidate):
                    yield candidate


def should_scan_file(path: Path) -> bool:
    return path.suffix.lower() not in SKIPPED_SUFFIXES


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        print(f"warning: could not read {path}: {exc}", file=sys.stderr)
        return None

    if b"\0" in data:
        return None

    return data.decode("utf-8", errors="replace")


def is_placeholder(secret: str) -> bool:
    normalized = secret.upper()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def scan_file(path: Path) -> Iterable[Finding]:
    text = read_text(path)
    if text is None:
        return

    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            for match in rule.pattern.finditer(line):
                secret = match.group(0)
                if is_placeholder(secret):
                    continue
                yield Finding(
                    path=path,
                    line_number=line_number,
                    rule_id=rule.rule_id,
                    secret=secret,
                )


def redact(secret: str) -> str:
    if len(secret) <= 8:
        return "***"
    return f"{secret[:4]}...{secret[-4:]}"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    roots = [Path(path) for path in args.paths]
    findings = [
        finding
        for path in iter_candidate_files(roots)
        for finding in scan_file(path)
    ]

    if not findings:
        print("Secret scan passed: no high-confidence secrets found.")
        return 0

    print("Secret scan failed: high-confidence secrets found.")
    for finding in findings:
        print(
            f"{finding.path}:{finding.line_number}: "
            f"{finding.rule_id}: {redact(finding.secret)}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
