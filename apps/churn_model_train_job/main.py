from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from churn_model_train_job.config import settings
from churn_model_train_job.training import ChurnTrainingRequest
from churn_model_train_job.training import train_churn_model

CHURN_MODEL_TRAIN_JOB_NAME = "churn_model_train"
WORKLOAD_NAME = "churn_model_train_job"


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def run_training() -> dict[str, Any]:
    trained_at = _utc_now()
    request = ChurnTrainingRequest(
        training_data_path=Path(settings.churn_training_data_path),
        output_dir=Path(settings.churn_model_output_dir),
        train_date=settings.churn_model_train_date or trained_at.date().isoformat(),
        run_id=settings.churn_model_run_id or trained_at.strftime("%Y%m%dT%H%M%SZ"),
        trained_at=trained_at,
    )
    manifest = train_churn_model(request)
    print(
        json.dumps(
            {
                "workload": WORKLOAD_NAME,
                "event": "churn_model_train_succeeded",
                "job_name": CHURN_MODEL_TRAIN_JOB_NAME,
                "timestamp": trained_at.isoformat(),
                **manifest,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return manifest


def main() -> None:
    run_training()


if __name__ == "__main__":
    main()
