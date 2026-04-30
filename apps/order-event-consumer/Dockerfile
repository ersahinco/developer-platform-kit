FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/backfill-worker/pyproject.toml apps/backfill-worker/pyproject.toml
COPY apps/data-export-job/pyproject.toml apps/data-export-job/pyproject.toml
COPY apps/order-event-consumer/pyproject.toml apps/order-event-consumer/pyproject.toml
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY packages/adapters/pyproject.toml packages/adapters/pyproject.toml
COPY apps/order-event-consumer/src apps/order-event-consumer/src
COPY packages/core/src packages/core/src
COPY packages/adapters/src packages/adapters/src
RUN uv sync --frozen --no-dev --package aws-sdlc-containers-order-event-consumer

FROM python:3.14-slim

RUN useradd --no-create-home --shell /bin/false app
USER app

WORKDIR /app/apps/order-event-consumer/src
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/order-event-consumer/src /app/apps/order-event-consumer/src
COPY --from=builder /app/packages/core/src /app/packages/core/src
COPY --from=builder /app/packages/adapters/src /app/packages/adapters/src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps/order-event-consumer/src:/app/packages/core/src:/app/packages/adapters/src"

CMD ["python", "-m", "aws_sdlc_order_event_consumer.main"]
