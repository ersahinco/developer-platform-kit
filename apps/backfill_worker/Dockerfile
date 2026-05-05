FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/backfill_worker/pyproject.toml apps/backfill_worker/pyproject.toml
COPY apps/data_export_job/pyproject.toml apps/data_export_job/pyproject.toml
COPY apps/order_event_consumer/pyproject.toml apps/order_event_consumer/pyproject.toml
COPY packages/domain/pyproject.toml packages/domain/pyproject.toml
COPY packages/application/pyproject.toml packages/application/pyproject.toml
COPY packages/infrastructure/pyproject.toml packages/infrastructure/pyproject.toml
COPY apps/backfill_worker apps/backfill_worker
COPY packages/domain packages/domain
COPY packages/application packages/application
COPY packages/infrastructure packages/infrastructure
RUN uv sync --frozen --no-dev --package aws-sdlc-containers-backfill-worker

# Tag-only (no digest) — Trivy scans the built image in CI for CVEs before push.
# Digest pinning requires automated renewal (Renovate/Dependabot) to stay secure;
# without it, a stale digest is worse than a fresh tag + CVE scan.
FROM python:3.14-slim

# Non-root user — do not run application processes as root
RUN useradd --no-create-home --shell /bin/false app
USER app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/backfill_worker /app/apps/backfill_worker
COPY --from=builder /app/packages/domain /app/packages/domain
COPY --from=builder /app/packages/application /app/packages/application
COPY --from=builder /app/packages/infrastructure /app/packages/infrastructure

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps:/app/packages"

CMD ["python", "-m", "backfill_worker.main"]
