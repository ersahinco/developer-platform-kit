from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_dockerfiles import check_dockerfile  # noqa: E402


def write_dockerfile(repo: Path, path: str, content: str) -> Path:
    dockerfile = repo / path
    dockerfile.parent.mkdir(parents=True)
    dockerfile.write_text(content, encoding="utf-8")
    return dockerfile


def test_dockerfile_policy_accepts_tagged_multistage_non_root_app(tmp_path: Path) -> None:
    dockerfile = write_dockerfile(
        tmp_path,
        "apps/api/Dockerfile",
        """
FROM python:3.12-slim AS builder
WORKDIR /app
RUN true

FROM python:3.12-slim
RUN useradd --no-create-home app
USER app
CMD ["python", "-m", "example"]
""".lstrip(),
    )

    assert check_dockerfile(dockerfile, tmp_path) == []


def test_dockerfile_policy_rejects_latest_base_image(tmp_path: Path) -> None:
    dockerfile = write_dockerfile(
        tmp_path,
        "db/Dockerfile",
        """
FROM liquibase/liquibase:latest
USER liquibase
""".lstrip(),
    )

    assert check_dockerfile(dockerfile, tmp_path) == [
        "db/Dockerfile: base image 'liquibase/liquibase:latest' must use a non-latest tag or digest"
    ]


def test_dockerfile_policy_requires_non_root_final_user(tmp_path: Path) -> None:
    dockerfile = write_dockerfile(
        tmp_path,
        "apps/worker/Dockerfile",
        """
FROM python:3.12-slim AS builder
RUN true

FROM python:3.12-slim
USER root
""".lstrip(),
    )

    assert check_dockerfile(dockerfile, tmp_path) == [
        "apps/worker/Dockerfile: final stage USER must not be root"
    ]


def test_dockerfile_policy_requires_multistage_app_workloads(tmp_path: Path) -> None:
    dockerfile = write_dockerfile(
        tmp_path,
        "apps/job/Dockerfile",
        """
FROM python:3.12-slim
USER app
""".lstrip(),
    )

    assert check_dockerfile(dockerfile, tmp_path) == [
        "apps/job/Dockerfile: app workload Dockerfiles must use a multi-stage build"
    ]
