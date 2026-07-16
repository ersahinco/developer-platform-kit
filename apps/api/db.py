from collections.abc import Iterator

from sqlalchemy.orm import Session

from api.config import settings
from infrastructure.db.session import transaction_pool_engine_and_session_factory


engine, SessionLocal = transaction_pool_engine_and_session_factory(
    str(settings.database_url)
)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
