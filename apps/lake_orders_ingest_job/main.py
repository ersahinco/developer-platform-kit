from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from lake_orders_ingest_job.config import settings
from lake_orders_ingest_job.pipeline import LakeOrdersIngestRequest
from lake_orders_ingest_job.pipeline import run_lake_orders_ingest

LAKE_ORDERS_INGEST_JOB_NAME = "lake_orders_ingest"
WORKLOAD_NAME = "lake_orders_ingest_job"


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def run_ingest() -> dict[str, Any]:
    ingested_at = _utc_now()
    request = LakeOrdersIngestRequest(
        source_dir=Path(settings.lake_orders_source_dir),
        output_dir=Path(settings.lake_orders_output_dir),
        ingest_date=settings.lake_orders_ingest_date or ingested_at.date().isoformat(),
        run_id=settings.lake_orders_run_id or ingested_at.strftime("%Y%m%dT%H%M%SZ"),
        ingested_at=ingested_at,
    )
    manifest = run_lake_orders_ingest(
        request=request,
        model_path=Path(__file__).resolve().parent
        / "models"
        / "curated_lake_orders.sql",
    )
    print(
        json.dumps(
            {
                "workload": WORKLOAD_NAME,
                "event": "lake_orders_ingest_succeeded",
                "job_name": LAKE_ORDERS_INGEST_JOB_NAME,
                "timestamp": ingested_at.isoformat(),
                **manifest,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return manifest


def main() -> None:
    run_ingest()


if __name__ == "__main__":
    main()
