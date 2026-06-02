from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import require_value


load_env_file()

_DEFAULT_SOURCE_DIR = str(Path(__file__).resolve().parent / "sample_data")
_DEFAULT_OUTPUT_DIR = "/tmp/aws-sdlc-containers-lake-orders"


@dataclass
class Settings:
    lake_orders_source_dir: str = field(
        default_factory=lambda: require_value(
            env_str("LAKE_ORDERS_SOURCE_DIR", _DEFAULT_SOURCE_DIR),
            "LAKE_ORDERS_SOURCE_DIR",
        )
    )
    lake_orders_output_dir: str = field(
        default_factory=lambda: require_value(
            env_str("LAKE_ORDERS_OUTPUT_DIR", _DEFAULT_OUTPUT_DIR),
            "LAKE_ORDERS_OUTPUT_DIR",
        )
    )
    lake_orders_run_id: str | None = field(
        default_factory=lambda: env_str("LAKE_ORDERS_RUN_ID")
    )
    lake_orders_ingest_date: str | None = field(
        default_factory=lambda: env_str("LAKE_ORDERS_INGEST_DATE")
    )


settings = Settings()
