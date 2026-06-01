from __future__ import annotations

import datetime
import json
from typing import Any

from open_dataset_pipeline.duckdb_store import (
    DuckDBOpenDatasetStore,
    OpenDatasetLoader,
)
from open_dataset_pipeline.pipeline import (
    OpenDatasetRequest,
    run_open_dataset_pipeline,
)
from open_dataset_pipeline.config import settings

OPEN_DATASET_PIPELINE_JOB_NAME = "open_dataset_pipeline"
WORKLOAD_NAME = "open_dataset_pipeline"


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def run_pipeline() -> dict[str, Any]:
    exported_at = _utc_now()
    request = OpenDatasetRequest(
        dataset_name=settings.required_open_dataset_name,
        source_url=settings.required_open_dataset_url,
        export_date=settings.open_dataset_date or exported_at.date().isoformat(),
        run_id=settings.open_dataset_run_id or exported_at.strftime("%Y%m%dT%H%M%SZ"),
        exported_at=exported_at,
    )
    manifest = run_open_dataset_pipeline(
        request=request,
        loader=OpenDatasetLoader(),
        store=DuckDBOpenDatasetStore(output_dir=settings.open_dataset_output_dir),
    )
    print(
        json.dumps(
            {
                "workload": WORKLOAD_NAME,
                "event": "open_dataset_pipeline_succeeded",
                "job_name": OPEN_DATASET_PIPELINE_JOB_NAME,
                "timestamp": exported_at.isoformat(),
                **manifest,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return manifest


def main() -> None:
    run_pipeline()


if __name__ == "__main__":
    main()
