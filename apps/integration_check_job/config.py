from dataclasses import dataclass
from dataclasses import field

from infrastructure.config import env_float
from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import require_value


load_env_file()

DEFAULT_OUTPUT_DIR = "/tmp/aws-sdlc-containers-integration-checks"


@dataclass
class Settings:
    integration_check_targets: str = field(
        default_factory=lambda: require_value(
            env_str("INTEGRATION_CHECK_TARGETS", ""),
            "INTEGRATION_CHECK_TARGETS",
        )
    )
    integration_check_timeout_seconds: float = field(
        default_factory=lambda: env_float("INTEGRATION_CHECK_TIMEOUT_SECONDS", 5.0)
    )
    integration_check_run_id: str | None = field(
        default_factory=lambda: env_str("INTEGRATION_CHECK_RUN_ID")
    )
    integration_check_output_dir: str = field(
        default_factory=lambda: require_value(
            env_str("INTEGRATION_CHECK_OUTPUT_DIR", DEFAULT_OUTPUT_DIR),
            "INTEGRATION_CHECK_OUTPUT_DIR",
        )
    )


settings = Settings()
