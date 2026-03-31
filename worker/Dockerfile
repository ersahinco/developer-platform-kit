FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.6.16 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ .

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "backfill.py"]
