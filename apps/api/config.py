from urllib.parse import quote

from pydantic import PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # PostgresDsn validates scheme, host, and path at startup — misconfigured
    # URLs fail immediately rather than at the first DB call.
    database_url: PostgresDsn | None = None

    # Runtime secret injection provides DB_PASSWORD. The full URL is composed
    # below so the password is never stored in plaintext deployment config.
    # db_host defaults to localhost for the colocated pgbouncer process.
    db_password: str | None = None
    db_user: str = "app"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "aws_sdlc_containers"
    otel_traces_enabled: bool = False
    otel_exporter_otlp_traces_endpoint: str | None = None
    otel_service_name: str = "aws-sdlc-containers-api"
    otel_deployment_environment: str = "local"
    rollout_drill_fault_mode: str = "off"
    rollout_drill_fault_paths: str = "/ready"
    rollout_drill_fault_status_code: int = 503
    rollout_drill_fault_delay_seconds: float = 3.0

    @model_validator(mode="after")
    def compose_database_url(self) -> "Settings":
        if self.database_url is None:
            if self.db_password is None:
                raise ValueError("Either DATABASE_URL or DB_PASSWORD must be set")
            db_user = quote(self.db_user, safe="")
            db_password = quote(self.db_password, safe="")
            self.database_url = PostgresDsn(
                f"postgresql://{db_user}:{db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return self


settings = Settings()
