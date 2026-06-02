from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from infrastructure.config import env_str
from infrastructure.config import load_env_file
from infrastructure.config import require_value


load_env_file()

_APP_ROOT = Path(__file__).resolve().parent
_DEFAULT_PROMPT_PATH = str(_APP_ROOT / "prompts" / "support_triage_v1.md")
_DEFAULT_EVAL_CASES_PATH = str(_APP_ROOT / "sample_data" / "evaluation_cases.json")
_DEFAULT_OUTPUT_DIR = "/tmp/aws-sdlc-containers-support-triage"


@dataclass
class Settings:
    service_port = 8083
    support_triage_prompt_path: str = field(
        default_factory=lambda: require_value(
            env_str("SUPPORT_TRIAGE_PROMPT_PATH", _DEFAULT_PROMPT_PATH),
            "SUPPORT_TRIAGE_PROMPT_PATH",
        )
    )
    support_triage_eval_cases_path: str = field(
        default_factory=lambda: require_value(
            env_str("SUPPORT_TRIAGE_EVAL_CASES_PATH", _DEFAULT_EVAL_CASES_PATH),
            "SUPPORT_TRIAGE_EVAL_CASES_PATH",
        )
    )
    support_triage_output_dir: str = field(
        default_factory=lambda: require_value(
            env_str("SUPPORT_TRIAGE_OUTPUT_DIR", _DEFAULT_OUTPUT_DIR),
            "SUPPORT_TRIAGE_OUTPUT_DIR",
        )
    )


settings = Settings()
