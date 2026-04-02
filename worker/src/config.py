from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Separate URL from the app's DATABASE_URL — worker connects directly to
    # Postgres, bypassing pgbouncer. Backfill transactions are long-running and
    # incompatible with pgbouncer's transaction-mode pool.
    backfill_database_url: str
    backfill_batch_size: int = 1000
    backfill_sleep_ms: int = 100


settings = Settings()
