import threading
import time

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from application.ports import ConfigStore
from infrastructure.db.models import AppRuntimeConfigModel

_TTL_SECONDS = 5  # re-read app_runtime_config at most every 5 seconds


class _ConfigCache:
    """Thread-safe TTL cache for a single app_runtime_config key."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: str | None = None
        self._expires_at: float = 0.0

    def get(self, session: Session, key: str) -> str:
        with self._lock:
            now = time.monotonic()
            if now < self._expires_at and self._value is not None:
                return self._value
            row = session.get(AppRuntimeConfigModel, key)
            if row is None:
                raise RuntimeError(
                    f"app_runtime_config row for '{key}' is missing — "
                    "ensure the DB was seeded correctly (Liquibase changeset 002)."
                )
            self._value = row.value
            self._expires_at = time.monotonic() + _TTL_SECONDS
            return self._value

    def invalidate(self) -> None:
        with self._lock:
            self._expires_at = 0.0


_read_mode_cache = _ConfigCache()
_write_mode_cache = _ConfigCache()


def read_mode_value(session: Session) -> str:
    return _read_mode_cache.get(session, "READ_MODE")


def write_mode_value(session: Session) -> str:
    return _write_mode_cache.get(session, "WRITE_MODE")


class SQLAlchemyConfigStore(ConfigStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> str | None:
        row = self._session.get(AppRuntimeConfigModel, key)
        return row.value if row else None

    def set(self, key: str, value: str) -> None:
        stmt = (
            pg_insert(AppRuntimeConfigModel)
            .values(key=key, value=value)
            .on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )
        self._session.execute(stmt)
        self._session.commit()
        if key == "READ_MODE":
            _read_mode_cache.invalidate()
        elif key == "WRITE_MODE":
            _write_mode_cache.invalidate()
