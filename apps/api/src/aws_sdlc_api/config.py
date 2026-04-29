from pydantic import PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # PostgresDsn validates scheme, host, and path at startup — misconfigured
    # URLs fail immediately rather than at the first DB call.
    database_url: PostgresDsn | None = None

    # ECS injects DB_PASSWORD from Secrets Manager. The full URL is composed
    # below so the password is never stored in the task definition plaintext.
    # db_host defaults to localhost (pgbouncer sidecar in the same ECS task).
    db_password: str | None = None
    db_user: str = "app"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "aws_sdlc_containers"
    order_events_queue_url: str | None = None

    @model_validator(mode="after")
    def compose_database_url(self) -> "Settings":
        if self.database_url is None:
            if self.db_password is None:
                raise ValueError("Either DATABASE_URL or DB_PASSWORD must be set")
            self.database_url = PostgresDsn(
                f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return self


settings = Settings()
