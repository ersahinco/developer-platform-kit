from __future__ import annotations

import os

_TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/aws_sdlc_containers"
os.environ.setdefault("DATABASE_URL", _TEST_DATABASE_URL)
os.environ.setdefault("BACKFILL_DATABASE_URL", _TEST_DATABASE_URL)
os.environ.setdefault("DATA_EXPORT_DATABASE_URL", _TEST_DATABASE_URL)

from api.config import Settings as ApiSettings  # noqa: E402
from backfill_worker.config import Settings as BackfillSettings  # noqa: E402
from data_export_job.config import Settings as DataExportSettings  # noqa: E402
from order_event_consumer.config import Settings as ConsumerSettings  # noqa: E402


def test_database_url_composition_escapes_secret_passwords(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BACKFILL_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATA_EXPORT_DATABASE_URL", raising=False)

    password = "pa:ss/word#with@reserved"
    expected_password = "pa%3Ass%2Fword%23with%40reserved"

    api = ApiSettings(database_url=None, db_password=password)
    consumer = ConsumerSettings(database_url=None, db_password=password)
    backfill = BackfillSettings(
        backfill_database_url=None,
        db_host="db.internal",
        db_password=password,
    )
    data_export = DataExportSettings(
        data_export_database_url=None,
        db_host="db.internal",
        db_password=password,
    )

    assert expected_password in str(api.database_url)
    assert expected_password in str(consumer.database_url)
    assert expected_password in backfill.required_backfill_database_url
    assert expected_password in data_export.required_data_export_database_url
