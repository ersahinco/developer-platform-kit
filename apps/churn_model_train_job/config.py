from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import require_value


load_env_file()

_DEFAULT_SOURCE_PATH = str(
    Path(__file__).resolve().parent / "sample_data" / "churn_training.csv"
)
_DEFAULT_OUTPUT_DIR = "/tmp/aws-sdlc-containers-churn-models"


@dataclass
class Settings:
    churn_training_data_path: str = field(
        default_factory=lambda: require_value(
            env_str("CHURN_TRAINING_DATA_PATH", _DEFAULT_SOURCE_PATH),
            "CHURN_TRAINING_DATA_PATH",
        )
    )
    churn_model_output_dir: str = field(
        default_factory=lambda: require_value(
            env_str("CHURN_MODEL_OUTPUT_DIR", _DEFAULT_OUTPUT_DIR),
            "CHURN_MODEL_OUTPUT_DIR",
        )
    )
    churn_model_run_id: str | None = field(
        default_factory=lambda: env_str("CHURN_MODEL_RUN_ID")
    )
    churn_model_train_date: str | None = field(
        default_factory=lambda: env_str("CHURN_MODEL_TRAIN_DATE")
    )


settings = Settings()
