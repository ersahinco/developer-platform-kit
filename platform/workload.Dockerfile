FROM python:3.14-slim AS builder

ARG APP_PATH
ARG UV_PACKAGE

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/backfill_worker/pyproject.toml apps/backfill_worker/pyproject.toml
COPY apps/booking_api/pyproject.toml apps/booking_api/pyproject.toml
COPY apps/churn_model_train_job/pyproject.toml apps/churn_model_train_job/pyproject.toml
COPY apps/churn_prediction_api/pyproject.toml apps/churn_prediction_api/pyproject.toml
COPY apps/data_export_job/pyproject.toml apps/data_export_job/pyproject.toml
COPY apps/event_consumer/pyproject.toml apps/event_consumer/pyproject.toml
COPY apps/integration_check_job/pyproject.toml apps/integration_check_job/pyproject.toml
COPY apps/lake_orders_ingest_job/pyproject.toml apps/lake_orders_ingest_job/pyproject.toml
COPY apps/operational_snapshot_job/pyproject.toml apps/operational_snapshot_job/pyproject.toml
COPY packages/domain/pyproject.toml packages/domain/pyproject.toml
COPY packages/application/pyproject.toml packages/application/pyproject.toml
COPY packages/infrastructure/pyproject.toml packages/infrastructure/pyproject.toml
COPY ${APP_PATH} ${APP_PATH}
COPY packages/domain packages/domain
COPY packages/application packages/application
COPY packages/infrastructure packages/infrastructure
RUN uv sync --frozen --no-dev --package ${UV_PACKAGE}

FROM python:3.14-slim

ARG APP_PATH
ARG WORKLOAD_CMD

RUN useradd --no-create-home --shell /bin/false app \
    && mkdir -p /exports \
    && chown app:app /exports
USER app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/${APP_PATH} /app/${APP_PATH}
COPY --from=builder /app/packages/domain /app/packages/domain
COPY --from=builder /app/packages/application /app/packages/application
COPY --from=builder /app/packages/infrastructure /app/packages/infrastructure

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps:/app/packages"
ENV WORKLOAD_CMD="${WORKLOAD_CMD}"

CMD ["sh", "-c", "exec ${WORKLOAD_CMD}"]
