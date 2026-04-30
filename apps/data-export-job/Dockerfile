FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/backfill-worker/pyproject.toml apps/backfill-worker/pyproject.toml
COPY apps/data-export-job/pyproject.toml apps/data-export-job/pyproject.toml
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY packages/adapters/pyproject.toml packages/adapters/pyproject.toml
COPY apps/data-export-job/src apps/data-export-job/src
RUN uv sync --frozen --no-dev --package aws-sdlc-containers-data-export-job

FROM python:3.14-slim

RUN useradd --no-create-home --shell /bin/false app
RUN mkdir -p /exports && chown app:app /exports
USER app

WORKDIR /app/apps/data-export-job/src
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/data-export-job/src /app/apps/data-export-job/src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps/data-export-job/src"

CMD ["python", "-m", "aws_sdlc_data_export_job.main"]
