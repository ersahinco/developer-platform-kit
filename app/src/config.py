from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    write_mode: Literal["legacy", "dual", "new"] = "legacy"
    read_mode: Literal["legacy", "new"] = "legacy"


settings = Settings()
