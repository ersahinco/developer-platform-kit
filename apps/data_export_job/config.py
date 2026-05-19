from dataclasses import dataclass
from dataclasses import field

from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import PostgresRuntimeSettings
from infrastructure.config import require_value


load_env_file()


@dataclass
class Settings(PostgresRuntimeSettings):
    data_export_database_url: str | None = field(
        default_factory=lambda: env_str("DATA_EXPORT_DATABASE_URL")
    )
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
    data_export_s3_bucket: str | None = field(
        default_factory=lambda: env_str("DATA_EXPORT_S3_BUCKET")
    )

    def __post_init__(self) -> None:
        self.data_export_database_url = self.resolve_database_url(
            database_url=self.data_export_database_url,
            env_name="DATA_EXPORT_DATABASE_URL",
        )

    @property
    def required_data_export_database_url(self) -> str:
        return require_value(self.data_export_database_url, "DATA_EXPORT_DATABASE_URL")


settings = Settings()
