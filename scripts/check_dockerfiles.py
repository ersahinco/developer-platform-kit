from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DOCKERFILE_PREFIX = "apps/"


def _tracked_dockerfiles(repo_root: Path = REPO_ROOT) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*Dockerfile"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [repo_root / line for line in result.stdout.splitlines() if line]


def _instruction(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    parts = stripped.split(maxsplit=1)
    if len(parts) != 2:
        return None

    return parts[0].upper(), parts[1].strip()


def _from_image(argument: str) -> str:
    return argument.split(maxsplit=1)[0]


def _is_tagged_image(image: str) -> bool:
    if "@" in image:
        return True

    name = image.rsplit("/", 1)[-1]
    if ":" not in name:
        return False

    return not name.endswith(":latest")


def check_dockerfile(path: Path, repo_root: Path = REPO_ROOT) -> list[str]:
    rel_path = path.relative_to(repo_root).as_posix()
    instructions = [
        parsed
        for line in path.read_text(encoding="utf-8").splitlines()
        if (parsed := _instruction(line)) is not None
    ]
    from_images = [
        _from_image(argument) for instruction, argument in instructions if instruction == "FROM"
    ]
    failures: list[str] = []

    for image in from_images:
        if not _is_tagged_image(image):
            failures.append(f"{rel_path}: base image {image!r} must use a non-latest tag or digest")

    if rel_path.startswith(APP_DOCKERFILE_PREFIX) and len(from_images) < 2:
        failures.append(f"{rel_path}: app workload Dockerfiles must use a multi-stage build")

    final_user = None
    for instruction, argument in instructions:
        if instruction == "FROM":
            final_user = None
        elif instruction == "USER":
            final_user = argument

    if final_user is None:
        failures.append(f"{rel_path}: final stage must declare a non-root USER")
    elif final_user.split(":", 1)[0] in {"root", "0"}:
        failures.append(f"{rel_path}: final stage USER must not be root")

    return failures


def main() -> int:
    failures: list[str] = []
    for dockerfile in _tracked_dockerfiles():
        failures.extend(check_dockerfile(dockerfile))

    if failures:
        print("Dockerfile policy check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print("Dockerfile policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
