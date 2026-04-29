from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.dependency_audit import build_audit_command, build_export_command  # noqa: E402


def test_export_command_uses_frozen_workspace_lock() -> None:
    requirements_path = Path("/tmp/requirements.txt")

    command = build_export_command(requirements_path)

    assert command == [
        "uv",
        "--quiet",
        "export",
        "--format",
        "requirements.txt",
        "--all-packages",
        "--all-groups",
        "--no-emit-project",
        "--no-emit-workspace",
        "--frozen",
        "--output-file",
        str(requirements_path),
    ]


def test_audit_command_checks_hashed_exported_pins_without_pip_resolution() -> None:
    requirements_path = Path("/tmp/requirements.txt")

    command = build_audit_command(requirements_path)

    assert command == [
        "uv",
        "run",
        "pip-audit",
        "-r",
        str(requirements_path),
        "--disable-pip",
        "--require-hashes",
        "--progress-spinner",
        "off",
        "--desc",
        "off",
        "--aliases",
        "off",
    ]
