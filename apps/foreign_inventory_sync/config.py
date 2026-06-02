from dataclasses import dataclass
from dataclasses import field

from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import PostgresRuntimeSettings


load_env_file()


@dataclass
class Settings(PostgresRuntimeSettings):
    service_port = 8080
    database_url: str | None = field(default_factory=lambda: env_str("DATABASE_URL"))
    db_host: str | None = field(default_factory=lambda: env_str("DB_HOST", "localhost"))

    def __post_init__(self) -> None:
        self.database_url = self.resolve_database_url(
            database_url=self.database_url,
            env_name="DATABASE_URL",
            default_db_host="localhost",
        )


settings = Settings()
