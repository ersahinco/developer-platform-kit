from dataclasses import dataclass
from dataclasses import field

from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import require_value


load_env_file()


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
            env_str(
                "OPEN_DATASET_OUTPUT_DIR", "/tmp/aws-sdlc-containers-open-datasets"
            ),
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
