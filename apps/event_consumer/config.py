from dataclasses import dataclass
from dataclasses import field

from infrastructure.config import env_bool
from infrastructure.config import env_float
from infrastructure.config import env_int
from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import PostgresRuntimeSettings
from infrastructure.config import require_value


load_env_file()


@dataclass
class Settings(PostgresRuntimeSettings):
    database_url: str | None = field(default_factory=lambda: env_str("DATABASE_URL"))
    db_host: str | None = field(default_factory=lambda: env_str("DB_HOST", "localhost"))
    event_consumer_worker_mode: str = field(
        default_factory=lambda: require_value(
            env_str("EVENT_CONSUMER_WORKER_MODE", "both"), "EVENT_CONSUMER_WORKER_MODE"
        )
    )
    event_consumer_worker_run_once: bool = field(
        default_factory=lambda: env_bool("EVENT_CONSUMER_WORKER_RUN_ONCE")
    )
    event_consumer_relay_batch_size: int = field(
        default_factory=lambda: env_int("EVENT_CONSUMER_RELAY_BATCH_SIZE", 10)
    )
    event_consumer_idle_sleep_seconds: float = field(
        default_factory=lambda: env_float("EVENT_CONSUMER_IDLE_SLEEP_SECONDS", 1.0)
    )
    event_consumer_pubsub_name: str = field(
        default_factory=lambda: require_value(
            env_str("EVENT_CONSUMER_PUBSUB_NAME", "async-events-pubsub"),
            "EVENT_CONSUMER_PUBSUB_NAME",
        )
    )
    event_consumer_topic: str = field(
        default_factory=lambda: require_value(
            env_str("EVENT_CONSUMER_TOPIC", "order-created-v1.fifo"),
            "EVENT_CONSUMER_TOPIC",
        )
    )
    event_consumer_app_port: int = field(
        default_factory=lambda: env_int("EVENT_CONSUMER_APP_PORT", 8081)
    )
    dapr_http_port: int = field(default_factory=lambda: env_int("DAPR_HTTP_PORT", 3500))
    dapr_http_endpoint: str | None = field(
        default_factory=lambda: env_str("DAPR_HTTP_ENDPOINT")
    )

    def __post_init__(self) -> None:
        if self.event_consumer_worker_mode not in {"relay", "consumer", "both"}:
            raise ValueError(
                "EVENT_CONSUMER_WORKER_MODE must be relay, consumer, or both"
            )
        self.database_url = self.resolve_database_url(
            database_url=self.database_url,
            env_name="DATABASE_URL",
            default_db_host="localhost",
        )

    @property
    def dapr_publish_endpoint(self) -> str:
        endpoint = self.dapr_http_endpoint
        if endpoint is None:
            endpoint = f"http://localhost:{self.dapr_http_port}"
        return endpoint.rstrip("/")


settings = Settings()
