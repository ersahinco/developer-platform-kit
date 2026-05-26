from dataclasses import dataclass
from dataclasses import field
import os
from pathlib import Path


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


def _clean_env_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "'\"":
        return stripped[1:-1]
    return stripped


load_env_file()

_DEFAULT_OUTPUT_DIR = "/tmp/aws-sdlc-containers-open-datasets"


@dataclass
class Settings:
    open_dataset_url: str | None = field(
        default_factory=lambda: env_str("OPEN_DATASET_URL")
    )
    open_dataset_name: str | None = field(
        default_factory=lambda: env_str("OPEN_DATASET_NAME")
    )
    open_dataset_output_dir: str = field(
        default_factory=lambda: require_value(
            env_str("OPEN_DATASET_OUTPUT_DIR", _DEFAULT_OUTPUT_DIR),
            "OPEN_DATASET_OUTPUT_DIR",
        )
    )
    open_dataset_run_id: str | None = field(
        default_factory=lambda: env_str("OPEN_DATASET_RUN_ID")
    )
    open_dataset_date: str | None = field(
        default_factory=lambda: env_str("OPEN_DATASET_DATE")
    )

    @property
    def required_open_dataset_url(self) -> str:
        return require_value(self.open_dataset_url, "OPEN_DATASET_URL")

    @property
    def required_open_dataset_name(self) -> str:
        return require_value(self.open_dataset_name, "OPEN_DATASET_NAME")


settings = Settings()
