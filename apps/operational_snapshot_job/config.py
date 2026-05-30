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
    operational_snapshot_run_id: str | None = field(
        default_factory=lambda: env_str("OPERATIONAL_SNAPSHOT_RUN_ID")
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
