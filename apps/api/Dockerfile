FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/backfill-worker/pyproject.toml apps/backfill-worker/pyproject.toml
COPY apps/data-export-job/pyproject.toml apps/data-export-job/pyproject.toml
COPY apps/order-event-consumer/pyproject.toml apps/order-event-consumer/pyproject.toml
COPY packages/domain/pyproject.toml packages/domain/pyproject.toml
COPY packages/application/pyproject.toml packages/application/pyproject.toml
COPY packages/infrastructure/pyproject.toml packages/infrastructure/pyproject.toml
COPY apps/api/src apps/api/src
COPY packages/domain/src packages/domain/src
COPY packages/application/src packages/application/src
COPY packages/infrastructure/src packages/infrastructure/src
RUN uv sync --frozen --no-dev --package aws-sdlc-containers-api

# ── Runtime ───────────────────────────────────────────────────────────────────
# Tag-only (no digest) — Trivy scans the built image in CI for CVEs before push.
# Digest pinning requires automated renewal (Renovate/Dependabot) to stay secure;
# without it, a stale digest is worse than a fresh tag + CVE scan.
FROM python:3.14-slim

# Non-root user — do not run application processes as root
RUN useradd --no-create-home --shell /bin/false app
USER app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/api/src /app/apps/api/src
COPY --from=builder /app/packages/domain/src /app/packages/domain/src
COPY --from=builder /app/packages/application/src /app/packages/application/src
COPY --from=builder /app/packages/infrastructure/src /app/packages/infrastructure/src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps/api/src:/app/packages/application/src:/app/packages/domain/src:/app/packages/infrastructure/src"

HEALTHCHECK --interval=5s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "aws_sdlc_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
