from dataclasses import dataclass
from dataclasses import field

from infrastructure.config import compose_postgres_url
from infrastructure.config import env_bool
from infrastructure.config import env_float
from infrastructure.config import env_int
from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import require_value
from infrastructure.config import validate_postgres_url


load_env_file()


@dataclass
class Settings:
    database_url: str | None = field(default_factory=lambda: env_str("DATABASE_URL"))
    db_password: str | None = field(default_factory=lambda: env_str("DB_PASSWORD"))
    db_user: str = field(
        default_factory=lambda: require_value(env_str("DB_USER", "app"), "DB_USER")
    )
    db_host: str = field(
        default_factory=lambda: require_value(
            env_str("DB_HOST", "localhost"), "DB_HOST"
        )
    )
    db_port: int = field(default_factory=lambda: env_int("DB_PORT", 5432))
    db_name: str = field(
        default_factory=lambda: require_value(
            env_str("DB_NAME", "aws_sdlc_containers"), "DB_NAME"
        )
    )
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
        if self.database_url is None:
            if self.db_password is None:
                raise ValueError("Either DATABASE_URL or DB_PASSWORD must be set")
            self.database_url = compose_postgres_url(
                db_user=self.db_user,
                db_password=self.db_password,
                db_host=self.db_host,
                db_port=self.db_port,
                db_name=self.db_name,
            )
        self.database_url = validate_postgres_url(self.database_url)

    @property
    def dapr_publish_endpoint(self) -> str:
        endpoint = self.dapr_http_endpoint
        if endpoint is None:
            endpoint = f"http://localhost:{self.dapr_http_port}"
        return endpoint.rstrip("/")


settings = Settings()
