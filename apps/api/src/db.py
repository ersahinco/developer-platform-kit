from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from config import settings

# NullPool: pgbouncer (transaction mode) manages the server-side connection pool.
# SQLAlchemy does not need its own pool on top — each checkout opens a new
# pgbouncer client connection, which pgbouncer maps to a pooled server connection.
# Stacking two pools would hold server connections idle inside SQLAlchemy's pool,
# defeating pgbouncer's multiplexing.
engine = create_engine(
    str(settings.database_url),
    poolclass=NullPool,
    # pool_pre_ping is omitted — it is a no-op with NullPool because every
    # connection is opened fresh per request; there is nothing to ping.
)
SessionLocal = sessionmaker(engine, autoflush=False)
# autoflush=False: with NullPool and short-lived per-request sessions there is
# no benefit to implicit flushes before queries, and disabling it avoids
# surprising DB round-trips inside read paths.


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
