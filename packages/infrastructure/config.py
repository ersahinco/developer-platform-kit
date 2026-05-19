from dataclasses import dataclass
from dataclasses import field
import os
from pathlib import Path
from urllib.parse import quote
from urllib.parse import urlparse


def compose_postgres_url(
    *,
    db_user: str,
    db_password: str,
    db_host: str,
    db_port: int,
    db_name: str,
) -> str:
    user = quote(db_user, safe="")
    password = quote(db_password, safe="")
    return f"postgresql://{user}:{password}@{db_host}:{db_port}/{db_name}"


def require_value(value: str | None, name: str) -> str:
    if value is None:
        raise RuntimeError(f"{name} was not configured")
    return value


def load_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _clean_env_value(value)


def env_str(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def env_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return int(value)


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None else float(value)


def validate_postgres_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("database URL must use postgres or postgresql scheme")
    if not parsed.hostname or parsed.path in {"", "/"}:
        raise ValueError("database URL must include host and database name")
    return value


@dataclass
class PostgresRuntimeSettings:
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

    def resolve_database_url(
        self,
        *,
        database_url: str | None,
        env_name: str,
        default_db_host: str | None = None,
        validate: bool = True,
    ) -> str:
        if database_url is None:
            if self.db_password is None:
                raise ValueError(f"Either {env_name} or DB_PASSWORD must be set")
            db_host = self.db_host if self.db_host is not None else default_db_host
            if db_host is None:
                raise ValueError(
                    f"Either {env_name} or DB_PASSWORD+DB_HOST must be set"
                )
            database_url = compose_postgres_url(
                db_user=self.db_user,
                db_password=self.db_password,
                db_host=db_host,
                db_port=self.db_port,
                db_name=self.db_name,
            )
        return validate_postgres_url(database_url) if validate else database_url


def _clean_env_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "'\"":
        return stripped[1:-1]
    return stripped
