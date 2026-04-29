from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def build_export_command(requirements_path: Path) -> list[str]:
    return [
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


def build_audit_command(requirements_path: Path) -> list[str]:
    return [
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


def run(command: Sequence[str], *, cwd: Path) -> int:
    print(f"+ {' '.join(command)}", flush=True)
    return subprocess.run(command, cwd=cwd, check=False).returncode


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aws-sdlc-dependency-audit-") as tmpdir:
        requirements_path = Path(tmpdir) / "requirements.txt"

        export_exit = run(build_export_command(requirements_path), cwd=ROOT)
        if export_exit != 0:
            return export_exit

        return run(build_audit_command(requirements_path), cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
