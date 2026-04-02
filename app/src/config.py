from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # PostgresDsn validates scheme, host, and path at startup — misconfigured
    # URLs fail immediately rather than at the first DB call.
    database_url: PostgresDsn


settings = Settings()
