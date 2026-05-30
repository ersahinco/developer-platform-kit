from typing import Any

from sqlalchemy import create_engine, text

from application.operational_snapshot import OperationalSnapshotState


TABLE_COUNTS = {
    "customers_count": "customers",
    "orders_count": "orders",
    "order_contact_email_count": "order_contact_email",
    "event_receipts_count": "event_receipts",
}


class SQLAlchemyOperationalSnapshotReader:
    def __init__(self, *, database_url: str) -> None:
        self._database_url = database_url

    def read(self) -> OperationalSnapshotState:
        engine = create_engine(
            self._database_url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
        )
        try:
            with engine.begin() as conn:
                counts = {
                    field: _table_count(conn, table_name)
                    for field, table_name in TABLE_COUNTS.items()
                }
                return OperationalSnapshotState(
                    read_mode=_runtime_mode(conn, "READ_MODE", default="legacy"),
                    write_mode=_runtime_mode(conn, "WRITE_MODE", default="legacy"),
                    outbox_pending_count=_outbox_pending_count(conn),
                    **counts,
                )
        finally:
            engine.dispose()


def _table_exists(conn: Any, table_name: str) -> bool:
    row = conn.execute(
        text("SELECT to_regclass(:table_name)"),
        {"table_name": table_name},
    ).fetchone()
    return row is not None and row[0] is not None


def _table_count(conn: Any, table_name: str) -> int:
    if not _table_exists(conn, table_name):
        return 0
    return int(conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0)


def _runtime_mode(conn: Any, key: str, *, default: str) -> str:
    if not _table_exists(conn, "app_runtime_config"):
        return default
    value = conn.execute(
        text("SELECT value FROM app_runtime_config WHERE key=:key"),
        {"key": key},
    ).scalar()
    return str(value or default)


def _outbox_pending_count(conn: Any) -> int:
    if not _table_exists(conn, "outbox_messages"):
        return 0
    return int(
        conn.execute(
            text("SELECT COUNT(*) FROM outbox_messages WHERE status = 'pending'")
        ).scalar()
        or 0
    )
