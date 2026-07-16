from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


def engine_and_session_factory(
    database_url: str,
) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(database_url, pool_pre_ping=True)
    return engine, sessionmaker(engine)


def transaction_pool_engine_and_session_factory(
    database_url: str,
) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(database_url, poolclass=NullPool)
    return engine, sessionmaker(engine, autoflush=False)


def ping_database(session: Session) -> None:
    session.execute(text("SELECT 1"))
