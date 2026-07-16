#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
HYBRID_ROOTS = (
    Path("infra/hybrid-reference/data"),
    Path("infra/hybrid-reference/compute"),
    Path("infra/hybrid-reference/dns"),
)
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
PLAN_ACTION = re.compile(
    r"^\s*#\s+(?P<address>[a-zA-Z0-9_.\[\]\"-]+)\s+will be\s+(?P<action>created|updated|destroyed)",
    re.MULTILINE,
)


def plan_actions(output: str) -> set[tuple[str, str]]:
    clean = ANSI_ESCAPE.sub("", output)
    return {
        (match.group("address"), match.group("action"))
        for match in PLAN_ACTION.finditer(clean)
    }


def _completed(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed in {cwd}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    return completed


def _run(tool: str, root: Path) -> set[tuple[str, str]]:
    init_command = [tool, "init", "-backend=false", "-input=false"]
    if tool == "terraform":
        init_command.append("-lockfile=readonly")
    _completed(init_command, root)
    completed = _completed(
        [tool, "test", "-verbose"],
        root,
    )
    actions = plan_actions(completed.stdout)
    if not actions:
        raise RuntimeError(f"{tool} produced no planned resource actions for {root}")
    return actions


def main() -> int:
    for tool in ("terraform", "tofu"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} is required for compatibility proof")

    with tempfile.TemporaryDirectory(prefix="iac-compatibility-") as temp_dir:
        temp = Path(temp_dir)
        for root in HYBRID_ROOTS:
            working_roots: dict[str, Path] = {}
            for tool in ("terraform", "tofu"):
                working_root = temp / tool / root.name
                shutil.copytree(
                    ROOT / root,
                    working_root,
                    ignore=shutil.ignore_patterns(".terraform"),
                )
                working_roots[tool] = working_root
            terraform_actions = _run("terraform", working_roots["terraform"])
            tofu_actions = _run("tofu", working_roots["tofu"])
            if terraform_actions != tofu_actions:
                raise RuntimeError(
                    f"Terraform/OpenTofu planned actions differ for {root}: "
                    f"terraform={sorted(terraform_actions)}, tofu={sorted(tofu_actions)}"
                )
            print(f"{root}: {len(terraform_actions)} matching planned resource actions")

    print("Terraform is authoritative; OpenTofu compatibility proof passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
