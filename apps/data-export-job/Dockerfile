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
COPY apps/data-export-job/src apps/data-export-job/src
COPY packages/domain/src packages/domain/src
COPY packages/application/src packages/application/src
COPY packages/infrastructure/src packages/infrastructure/src
RUN uv sync --frozen --no-dev --package aws-sdlc-containers-data-export-job

FROM python:3.14-slim

RUN useradd --no-create-home --shell /bin/false app
RUN mkdir -p /exports && chown app:app /exports
USER app

WORKDIR /app/apps/data-export-job/src
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/data-export-job/src /app/apps/data-export-job/src
COPY --from=builder /app/packages/domain/src /app/packages/domain/src
COPY --from=builder /app/packages/application/src /app/packages/application/src
COPY --from=builder /app/packages/infrastructure/src /app/packages/infrastructure/src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps/data-export-job/src:/app/packages/application/src:/app/packages/domain/src:/app/packages/infrastructure/src"

CMD ["python", "-m", "aws_sdlc_data_export_job.main"]
