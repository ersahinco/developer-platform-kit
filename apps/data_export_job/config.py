from dataclasses import dataclass
from dataclasses import field

from infrastructure.config import compose_postgres_url
from infrastructure.config import env_int
from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import require_value


load_env_file()


@dataclass
class Settings:
    data_export_database_url: str | None = field(
        default_factory=lambda: env_str("DATA_EXPORT_DATABASE_URL")
    )
    db_password: str | None = field(default_factory=lambda: env_str("DB_PASSWORD"))
    db_user: str = field(
        default_factory=lambda: require_value(env_str("DB_USER", "app"), "DB_USER")
    )
    db_host: str | None = field(default_factory=lambda: env_str("DB_HOST"))
    db_port: int = field(default_factory=lambda: env_int("DB_PORT", 5432))
    db_name: str = field(
        default_factory=lambda: require_value(
            env_str("DB_NAME", "aws_sdlc_containers"), "DB_NAME"
        )
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
        if self.data_export_database_url is None:
            if self.db_password is None or self.db_host is None:
                raise ValueError(
                    "Either DATA_EXPORT_DATABASE_URL or DB_PASSWORD+DB_HOST must be set"
                )
            self.data_export_database_url = compose_postgres_url(
                db_user=self.db_user,
                db_password=self.db_password,
                db_host=self.db_host,
                db_port=self.db_port,
                db_name=self.db_name,
            )

    @property
    def required_data_export_database_url(self) -> str:
        return require_value(self.data_export_database_url, "DATA_EXPORT_DATABASE_URL")


settings = Settings()
