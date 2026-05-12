from urllib.parse import quote

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Export jobs connect directly to Postgres. They can run longer reads than
    # request traffic and should not occupy pgbouncer transaction-pool slots.
    data_export_database_url: str | None = None

    # Runtime secret injection provides DB_PASSWORD while host/user remain
    # non-sensitive environment variables.
    db_password: str | None = None
    db_user: str = "app"
    db_host: str | None = None
    db_port: int = 5432
    db_name: str = "aws_sdlc_containers"

    data_export_output_dir: str = "/tmp/aws-sdlc-containers-data-hub"
    data_export_run_id: str | None = None
    data_export_date: str | None = None
    data_export_s3_bucket: str | None = None

    @model_validator(mode="after")
    def compose_export_url(self) -> "Settings":
        if self.data_export_database_url is None:
            if self.db_password is None or self.db_host is None:
                raise ValueError(
                    "Either DATA_EXPORT_DATABASE_URL or DB_PASSWORD+DB_HOST must be set"
                )
            db_user = quote(self.db_user, safe="")
            db_password = quote(self.db_password, safe="")
            self.data_export_database_url = (
                f"postgresql://{db_user}:{db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return self

    @property
    def required_data_export_database_url(self) -> str:
        if self.data_export_database_url is None:
            raise RuntimeError("DATA_EXPORT_DATABASE_URL was not configured")
        return self.data_export_database_url


settings = Settings()
