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
COPY apps/order_event_consumer apps/order_event_consumer
COPY packages/domain packages/domain
COPY packages/application packages/application
COPY packages/infrastructure packages/infrastructure
RUN uv sync --frozen --no-dev --package aws-sdlc-containers-order-event-consumer

FROM python:3.14-slim

RUN useradd --no-create-home --shell /bin/false app
USER app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/order_event_consumer /app/apps/order_event_consumer
COPY --from=builder /app/packages/domain /app/packages/domain
COPY --from=builder /app/packages/application /app/packages/application
COPY --from=builder /app/packages/infrastructure /app/packages/infrastructure

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps:/app/packages"

CMD ["python", "-m", "order_event_consumer.main"]
