from dataclasses import dataclass
from dataclasses import field

from infrastructure.config import env_int
from infrastructure.config import env_optional_int
from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import PostgresRuntimeSettings
from infrastructure.config import require_value


load_env_file()


@dataclass
class Settings(PostgresRuntimeSettings):
    database_url: str | None = field(default_factory=lambda: env_str("DATABASE_URL"))
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
        self.database_url = self.resolve_database_url(
            database_url=self.database_url,
            env_name="DATABASE_URL",
        )
        if self.backfill_max_batches is not None and self.backfill_max_batches < 1:
            raise ValueError("BACKFILL_MAX_BATCHES must be at least 1 when set")

    @property
    def required_database_url(self) -> str:
        return require_value(self.database_url, "DATABASE_URL")


settings = Settings()
