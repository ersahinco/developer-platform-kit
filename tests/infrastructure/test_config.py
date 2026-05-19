from infrastructure.config import PostgresRuntimeSettings
import pytest


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
            env_name="BACKFILL_DATABASE_URL",
        )
    assert str(exc.value) == (
        "Either BACKFILL_DATABASE_URL or DB_PASSWORD+DB_HOST must be set"
    )


def test_postgres_runtime_settings_validates_existing_url() -> None:
    settings = PostgresRuntimeSettings()

    resolved = settings.resolve_database_url(
        database_url="postgresql://user:secret@db.internal:5432/service_db",
        env_name="DATABASE_URL",
    )

    assert resolved == "postgresql://user:secret@db.internal:5432/service_db"
