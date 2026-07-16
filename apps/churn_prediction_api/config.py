from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from infrastructure.config import env_int
from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import require_value


load_env_file()

_DEFAULT_MODEL_PATH = str(
    Path(__file__).resolve().parent / "sample_model" / "churn_model.json"
)


@dataclass
class Settings:
    service_port: int = field(default_factory=lambda: env_int("SERVICE_PORT", 8082))
    churn_model_path: str = field(
        default_factory=lambda: require_value(
            env_str("CHURN_MODEL_PATH", _DEFAULT_MODEL_PATH),
            "CHURN_MODEL_PATH",
        )
    )


settings = Settings()
