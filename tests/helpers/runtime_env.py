from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlparse, urlunparse


_DEFAULT_DATABASE_URL = (
    "postgresql://postgres:postgres@localhost:6432/aws_sdlc_containers"
)


def direct_postgres_url(env: Mapping[str, str], *, key: str = "DATABASE_URL") -> str:
    db_url = env.get(key, _DEFAULT_DATABASE_URL)
    parsed = urlparse(db_url)
    host = parsed.hostname or "localhost"
    if host in {"db", "pgbouncer"}:
        host = "localhost"
    auth = f"{parsed.username}:{parsed.password}@" if parsed.username else ""
    direct = parsed._replace(netloc=f"{auth}{host}:5432")
    return urlunparse(direct)
