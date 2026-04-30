FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/backfill-worker/pyproject.toml apps/backfill-worker/pyproject.toml
COPY apps/data-export-job/pyproject.toml apps/data-export-job/pyproject.toml
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY packages/adapters/pyproject.toml packages/adapters/pyproject.toml
COPY apps/backfill-worker/src apps/backfill-worker/src
RUN uv sync --frozen --no-dev --package aws-sdlc-containers-backfill-worker

# Tag-only (no digest) — Trivy scans the built image in CI for CVEs before push.
# Digest pinning requires automated renewal (Renovate/Dependabot) to stay secure;
# without it, a stale digest is worse than a fresh tag + CVE scan.
FROM python:3.14-slim

# Non-root user — do not run application processes as root
RUN useradd --no-create-home --shell /bin/false app
USER app

WORKDIR /app/apps/backfill-worker/src
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/backfill-worker/src /app/apps/backfill-worker/src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps/backfill-worker/src"

CMD ["python", "-m", "aws_sdlc_backfill_worker.main"]
