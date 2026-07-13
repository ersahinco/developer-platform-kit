import os

import pytest

from infrastructure.config import load_env_file
from infrastructure.config import PostgresRuntimeSettings


def test_load_env_file_uses_shared_dotenv_rules(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPEN_DATASET_NAME='iris data'",
                'OPEN_DATASET_URL="file:///tmp/iris.csv"',
                "OPEN_DATASET_OUTPUT_DIR=/tmp/open-datasets",
                "OPEN_DATASET_RUN_ID=from-file",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPEN_DATASET_NAME", raising=False)
    monkeypatch.delenv("OPEN_DATASET_URL", raising=False)
    monkeypatch.delenv("OPEN_DATASET_OUTPUT_DIR", raising=False)
    monkeypatch.setenv("OPEN_DATASET_RUN_ID", "already-set")

    load_env_file(env_file)

    assert os.environ["OPEN_DATASET_NAME"] == "iris data"
    assert os.environ["OPEN_DATASET_URL"] == "file:///tmp/iris.csv"
    assert os.environ["OPEN_DATASET_OUTPUT_DIR"] == "/tmp/open-datasets"
    assert os.environ["OPEN_DATASET_RUN_ID"] == "already-set"


def test_postgres_runtime_settings_can_compose_url_with_default_host() -> None:
    settings = PostgresRuntimeSettings(
        db_password="secret",
        db_host=None,
    )

    resolved = settings.resolve_database_url(
        database_url=None,
        env_name="DATABASE_URL",
        default_db_host="localhost",
    )

    assert resolved == "postgresql://app:secret@localhost:5432/aws_sdlc_containers"


def test_postgres_runtime_settings_requires_db_host_when_no_default() -> None:
    settings = PostgresRuntimeSettings(
        db_password="secret",
        db_host=None,
    )

    with pytest.raises(ValueError) as exc:
        settings.resolve_database_url(
            database_url=None,
            env_name="DATABASE_URL",
        )
    assert str(exc.value) == ("Either DATABASE_URL or DB_PASSWORD+DB_HOST must be set")


def test_postgres_runtime_settings_validates_existing_url() -> None:
    settings = PostgresRuntimeSettings()

    resolved = settings.resolve_database_url(
        database_url="postgresql://user:secret@db.internal:5432/service_db",
        env_name="DATABASE_URL",
    )

    assert resolved == "postgresql://user:secret@db.internal:5432/service_db"
