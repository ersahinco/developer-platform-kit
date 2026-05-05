from typing import Literal
from urllib.parse import quote

from pydantic import PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: PostgresDsn | None = None
    db_password: str | None = None
    db_user: str = "app"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "aws_sdlc_containers"

    order_events_worker_mode: Literal["relay", "consumer", "both"] = "both"
    order_events_worker_run_once: bool = False
    order_events_relay_batch_size: int = 10
    order_events_idle_sleep_seconds: float = 1.0
    order_events_pubsub_name: str = "order-events-pubsub"
    order_events_topic: str = "order-created-v1.fifo"
    order_events_app_port: int = 8081
    dapr_http_port: int = 3500
    dapr_http_endpoint: str | None = None

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

    @property
    def dapr_publish_endpoint(self) -> str:
        endpoint = self.dapr_http_endpoint
        if endpoint is None:
            endpoint = f"http://localhost:{self.dapr_http_port}"
        return endpoint.rstrip("/")


settings = Settings()
