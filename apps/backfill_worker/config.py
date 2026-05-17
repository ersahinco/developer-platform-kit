from dataclasses import dataclass
from dataclasses import field

from infrastructure.config import compose_postgres_url
from infrastructure.config import env_int
from infrastructure.config import env_optional_int
from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import require_value


load_env_file()


@dataclass
class Settings:
    backfill_database_url: str | None = field(
        default_factory=lambda: env_str("BACKFILL_DATABASE_URL")
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
    backfill_batch_size: int = field(
        default_factory=lambda: env_int("BACKFILL_BATCH_SIZE", 1000)
    )
    backfill_sleep_ms: int = field(
        default_factory=lambda: env_int("BACKFILL_SLEEP_MS", 100)
    )
    backfill_max_batches: int | None = field(
        default_factory=lambda: env_optional_int("BACKFILL_MAX_BATCHES")
    )

    def __post_init__(self) -> None:
        if self.backfill_database_url is None:
            if self.db_password is None or self.db_host is None:
                raise ValueError(
                    "Either BACKFILL_DATABASE_URL or DB_PASSWORD+DB_HOST must be set"
                )
            self.backfill_database_url = compose_postgres_url(
                db_user=self.db_user,
                db_password=self.db_password,
                db_host=self.db_host,
                db_port=self.db_port,
                db_name=self.db_name,
            )
        if self.backfill_max_batches is not None and self.backfill_max_batches < 1:
            raise ValueError("BACKFILL_MAX_BATCHES must be at least 1 when set")

    @property
    def required_backfill_database_url(self) -> str:
        return require_value(self.backfill_database_url, "BACKFILL_DATABASE_URL")


settings = Settings()
