#!/usr/bin/env python3
"""Build and push the API image used by the ECS app service."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        check=True,
        cwd=ROOT,
        input=input_text,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    return result.stdout


def _default_tag() -> str:
    short_sha = _run(["git", "rev-parse", "--short=12", "HEAD"]).strip()
    timestamp = dt.datetime.now(tz=dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"sha-local-{short_sha}-{timestamp}"


def main() -> int:
    region = os.environ.get("AWS_REGION", "eu-central-1")
    account_id = os.environ.get("ACCOUNT_ID", "691627364817")
    stack_name = os.environ.get("STACK_NAME", "aws-sdlc-containers")
    tag = os.environ.get("APP_IMAGE_TAG") or _default_tag()
    registry = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    image = f"{registry}/{stack_name}/app:{tag}"

    password = _run(["aws", "ecr", "get-login-password", "--region", region])
    _run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        input_text=password,
    )
    _run(
        [
            "docker",
            "build",
            "--platform",
            "linux/amd64",
            "-f",
            "apps/api/Dockerfile",
            "-t",
            image,
            ".",
        ]
    )
    _run(["docker", "push", image])

    print(f"APP_IMAGE_TAG={tag}")
    print(f"APP_IMAGE={image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
