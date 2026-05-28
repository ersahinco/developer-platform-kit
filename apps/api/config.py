from dataclasses import dataclass
from dataclasses import field

from infrastructure.config import env_bool
from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import PostgresRuntimeSettings
from infrastructure.config import require_value


load_env_file()


@dataclass
class Settings(PostgresRuntimeSettings):
    database_url: str | None = field(default_factory=lambda: env_str("DATABASE_URL"))
    db_host: str | None = field(default_factory=lambda: env_str("DB_HOST", "localhost"))
    primary_edge_auth_token: str | None = field(
        default_factory=lambda: env_str("PRIMARY_EDGE_AUTH_TOKEN")
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

    def __post_init__(self) -> None:
        self.database_url = self.resolve_database_url(
            database_url=self.database_url,
            env_name="DATABASE_URL",
            default_db_host="localhost",
        )


settings = Settings()
