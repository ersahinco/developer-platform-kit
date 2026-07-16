from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from churn_model_train_job.config import settings
from churn_model_train_job.training import ChurnTrainingRequest
from churn_model_train_job.training import train_churn_model

JOB_NAME = "churn_model_train"
WORKLOAD_NAME = "churn_model_train_job"


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.UTC)


def run_training() -> dict[str, Any]:
    trained_at = _utc_now()
    manifest = train_churn_model(
        ChurnTrainingRequest(
            training_data_path=Path(settings.churn_training_data_path),
            output_dir=Path(settings.churn_model_output_dir),
            train_date=settings.churn_model_train_date or trained_at.date().isoformat(),
            run_id=settings.churn_model_run_id or trained_at.strftime("%Y%m%dT%H%M%SZ"),
            trained_at=trained_at,
        )
    )
    print(
        json.dumps(
            {
                "workload": WORKLOAD_NAME,
                "event": "churn_model_train_succeeded",
                "job_name": JOB_NAME,
                "timestamp": trained_at.isoformat(),
                **manifest,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return manifest


def main() -> None:
    try:
        run_training()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "workload": WORKLOAD_NAME,
                    "event": "churn_model_train_failed",
                    "job_name": JOB_NAME,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "timestamp": _utc_now().isoformat(),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        raise


if __name__ == "__main__":
    main()
