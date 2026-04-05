FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.6.16 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

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
COPY src/ .

ENV PATH="/app/.venv/bin:$PATH"

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "adapters.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
