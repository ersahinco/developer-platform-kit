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
    otel_traces_enabled: bool = field(
        default_factory=lambda: env_bool("OTEL_TRACES_ENABLED")
    )
    otel_exporter_otlp_traces_endpoint: str | None = field(
        default_factory=lambda: env_str("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    )
    otel_service_name: str = field(
        default_factory=lambda: require_value(
            env_str("OTEL_SERVICE_NAME", "aws-sdlc-containers-api"),
            "OTEL_SERVICE_NAME",
        )
    )
    otel_deployment_environment: str = field(
        default_factory=lambda: require_value(
            env_str("OTEL_DEPLOYMENT_ENVIRONMENT", "local"),
            "OTEL_DEPLOYMENT_ENVIRONMENT",
        )
    )
    rollout_drill_fault_mode: str = field(
        default_factory=lambda: require_value(
            env_str("ROLLOUT_DRILL_FAULT_MODE", "off"), "ROLLOUT_DRILL_FAULT_MODE"
        )
    )
    rollout_drill_fault_paths: str = field(
        default_factory=lambda: require_value(
            env_str("ROLLOUT_DRILL_FAULT_PATHS", "/ready"),
            "ROLLOUT_DRILL_FAULT_PATHS",
        )
    )
    rollout_drill_fault_status_code: int = field(
        default_factory=lambda: env_int("ROLLOUT_DRILL_FAULT_STATUS_CODE", 503)
    )
    rollout_drill_fault_delay_seconds: float = field(
        default_factory=lambda: env_float("ROLLOUT_DRILL_FAULT_DELAY_SECONDS", 3.0)
    )

    def __post_init__(self) -> None:
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


settings = Settings()
