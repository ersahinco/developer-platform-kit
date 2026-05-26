FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /app

COPY examples/open_dataset_pipeline examples/open_dataset_pipeline

RUN uv venv /app/.venv \
    && /app/.venv/bin/python -m pip install --no-cache-dir \
      -e examples/open_dataset_pipeline

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/examples:/app/packages"

CMD ["python", "-m", "open_dataset_pipeline.main"]
