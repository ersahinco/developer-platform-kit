from dataclasses import dataclass
from dataclasses import field

from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import PostgresRuntimeSettings
from infrastructure.config import require_value


load_env_file()


@dataclass
class Settings(PostgresRuntimeSettings):
    database_url: str | None = field(default_factory=lambda: env_str("DATABASE_URL"))
    data_export_output_dir: str = field(
        default_factory=lambda: require_value(
            env_str("DATA_EXPORT_OUTPUT_DIR", "/tmp/aws-sdlc-containers-data-hub"),
            "DATA_EXPORT_OUTPUT_DIR",
        )
    )
    data_export_run_id: str | None = field(
        default_factory=lambda: env_str("DATA_EXPORT_RUN_ID")
    )
    data_export_date: str | None = field(
        default_factory=lambda: env_str("DATA_EXPORT_DATE")
    )
    data_export_bucket: str | None = field(
        default_factory=lambda: env_str("DATA_EXPORT_BUCKET")
    )

    def __post_init__(self) -> None:
        self.database_url = self.resolve_database_url(
            database_url=self.database_url,
            env_name="DATABASE_URL",
        )

    @property
    def required_database_url(self) -> str:
        return require_value(self.database_url, "DATABASE_URL")


settings = Settings()
