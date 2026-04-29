FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.6.16 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/backfill-worker/pyproject.toml apps/backfill-worker/pyproject.toml
COPY apps/data-export-job/pyproject.toml apps/data-export-job/pyproject.toml
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY packages/adapters/pyproject.toml packages/adapters/pyproject.toml
COPY apps/api/src apps/api/src
COPY packages/core/src packages/core/src
COPY packages/adapters/src packages/adapters/src
RUN uv sync --frozen --no-dev --package aws-sdlc-containers-app

# ── Runtime ───────────────────────────────────────────────────────────────────
# Tag-only (no digest) — Trivy scans the built image in CI for CVEs before push.
# Digest pinning requires automated renewal (Renovate/Dependabot) to stay secure;
# without it, a stale digest is worse than a fresh tag + CVE scan.
FROM python:3.12-slim

# Non-root user — do not run application processes as root
RUN useradd --no-create-home --shell /bin/false app
USER app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/api/src /app/apps/api/src
COPY --from=builder /app/packages/core/src /app/packages/core/src
COPY --from=builder /app/packages/adapters/src /app/packages/adapters/src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps/api/src:/app/packages/core/src:/app/packages/adapters/src"

HEALTHCHECK --interval=5s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "adapters.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
