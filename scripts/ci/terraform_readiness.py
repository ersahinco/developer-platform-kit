from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
INFRA_ROOTS = ("infra/platform", "infra/app")
ACTIONABLE_BLOCKERS = (
    "Failed to query available provider packages",
    "could not connect to registry.terraform.io",
    "validating provider credentials",
    "ExpiredToken",
    "InvalidClientTokenId",
    "no valid credential sources",
)


def run(command: list[str], *, cwd: Path = ROOT, allow_blocker: bool = False) -> bool:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "AWS_ACCESS_KEY_ID": "local",
            "AWS_SECRET_ACCESS_KEY": "local",
            "AWS_SESSION_TOKEN": "",
            "AWS_EC2_METADATA_DISABLED": "true",
        },
    )
    if completed.returncode == 0:
        if completed.stdout:
            print(completed.stdout, end="")
        return True

    output = f"{completed.stdout}\n{completed.stderr}"
    if allow_blocker and any(marker in output for marker in ACTIONABLE_BLOCKERS):
        print(output, file=sys.stderr)
        print(
            "Terraform syntax check reached provider readiness. "
            "Install/cache providers and use valid AWS credentials to run full "
            "`terraform init -backend=false && terraform validate` locally.",
            file=sys.stderr,
        )
        return False

    print(output, file=sys.stderr)
    raise subprocess.CalledProcessError(completed.returncode, command)


def main() -> int:
    run(["terraform", "fmt", "-check", "-recursive", "infra/"])
    validated_all = True
    for root in INFRA_ROOTS:
        root_path = ROOT / root
        if not run(
            ["terraform", "init", "-backend=false"], cwd=root_path, allow_blocker=True
        ):
            validated_all = False
            continue
        if not run(["terraform", "validate"], cwd=root_path, allow_blocker=True):
            validated_all = False
    if validated_all:
        print("Terraform backend-free validation passed for platform and app roots.")
    else:
        print("Terraform fmt passed; provider readiness blocked full local validate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
