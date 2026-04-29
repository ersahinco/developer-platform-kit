from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Separate URL from the app's DATABASE_URL — worker connects directly to
    # Postgres, bypassing pgbouncer. Backfill transactions are long-running and
    # incompatible with pgbouncer's transaction-mode pool.
    backfill_database_url: str | None = None

    # ECS injects DB_PASSWORD + DB_HOST from Secrets Manager / env. The full URL
    # is composed below so the password is never stored in the task definition plaintext.
    db_password: str | None = None
    db_user: str = "app"
    db_host: str | None = None
    db_port: int = 5432
    db_name: str = "aws_sdlc_containers"

    backfill_batch_size: int = 1000
    backfill_sleep_ms: int = 100

    @model_validator(mode="after")
    def compose_backfill_url(self) -> "Settings":
        if self.backfill_database_url is None:
            if self.db_password is None or self.db_host is None:
                raise ValueError(
                    "Either BACKFILL_DATABASE_URL or DB_PASSWORD+DB_HOST must be set"
                )
            self.backfill_database_url = f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        return self

    @property
    def required_backfill_database_url(self) -> str:
        if self.backfill_database_url is None:
            raise RuntimeError("BACKFILL_DATABASE_URL was not configured")
        return self.backfill_database_url


settings = Settings()
