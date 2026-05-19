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
    order_events_worker_mode: str = field(
        default_factory=lambda: require_value(
            env_str("ORDER_EVENTS_WORKER_MODE", "both"), "ORDER_EVENTS_WORKER_MODE"
        )
    )
    order_events_worker_run_once: bool = field(
        default_factory=lambda: env_bool("ORDER_EVENTS_WORKER_RUN_ONCE")
    )
    order_events_relay_batch_size: int = field(
        default_factory=lambda: env_int("ORDER_EVENTS_RELAY_BATCH_SIZE", 10)
    )
    order_events_idle_sleep_seconds: float = field(
        default_factory=lambda: env_float("ORDER_EVENTS_IDLE_SLEEP_SECONDS", 1.0)
    )
    order_events_pubsub_name: str = field(
        default_factory=lambda: require_value(
            env_str("ORDER_EVENTS_PUBSUB_NAME", "order-events-pubsub"),
            "ORDER_EVENTS_PUBSUB_NAME",
        )
    )
    order_events_topic: str = field(
        default_factory=lambda: require_value(
            env_str("ORDER_EVENTS_TOPIC", "order-created-v1.fifo"),
            "ORDER_EVENTS_TOPIC",
        )
    )
    order_events_app_port: int = field(
        default_factory=lambda: env_int("ORDER_EVENTS_APP_PORT", 8081)
    )
    dapr_http_port: int = field(default_factory=lambda: env_int("DAPR_HTTP_PORT", 3500))
    dapr_http_endpoint: str | None = field(
        default_factory=lambda: env_str("DAPR_HTTP_ENDPOINT")
    )

    def __post_init__(self) -> None:
        if self.order_events_worker_mode not in {"relay", "consumer", "both"}:
            raise ValueError(
                "ORDER_EVENTS_WORKER_MODE must be relay, consumer, or both"
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
