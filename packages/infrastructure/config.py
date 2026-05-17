from urllib.parse import quote


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
