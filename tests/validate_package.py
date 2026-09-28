"""Prove the built CLI works away from its checkout, with identical starter files."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent


def contents(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


def main() -> None:
    (wheel,) = Path(sys.argv[1]).resolve().glob("*.whl")
    with ZipFile(wheel) as archive:
        assert all(
            name.startswith("scaffold/") or ".dist-info/" in name for name in archive.namelist()
        ), "CLI wheel includes unrelated repository files"
        assert any(name.endswith("/licenses/LICENSE") for name in archive.namelist())

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(work / "venv")], check=True
        )
        binaries = work / "venv" / ("Scripts" if os.name == "nt" else "bin")
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(binaries / "python"),
                "--no-deps",
                "--no-index",
                str(wheel),
            ],
            check=True,
            cwd=work,
            env=env,
        )
        for command, module, options in (
            ("dpk", "scaffold.new_repo", ["render-examples"]),
            ("dpk-backstage", "scaffold.backstage", []),
        ):
            expected, actual = work / f"{command}-source", work / f"{command}-installed"
            subprocess.run(
                [sys.executable, "-m", module, *options, str(expected)], check=True, cwd=ROOT
            )
            subprocess.run(
                [str(binaries / command), *options, str(actual)], check=True, cwd=work, env=env
            )
            assert contents(actual) == contents(expected), f"{command} differs from the checkout"
    print("Installed CLI and Backstage export match all three checkout templates.")


if __name__ == "__main__":
    main()
