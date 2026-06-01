import datetime
import json
from typing import Any

from application.data_export import (
    DataExportRequest,
    run_order_contact_email_export,
)
from data_export_job.config import settings
from infrastructure.data_export import (
    LocalDataExportStore,
    S3DataExportPublisher,
    SQLAlchemyOrderContactEmailExportReader,
)

DATA_EXPORT_JOB_NAME = "order_contact_email_export"
WORKLOAD_NAME = "data_export_job"


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def run_export(s3_client: Any | None = None) -> dict[str, Any]:
    exported_at = _utc_now()
    request = DataExportRequest(
        export_date=settings.data_export_date or exported_at.date().isoformat(),
        run_id=settings.data_export_run_id or exported_at.strftime("%Y%m%dT%H%M%SZ"),
        exported_at=exported_at,
    )
    publisher = (
        S3DataExportPublisher(
            bucket=settings.data_export_s3_bucket,
            s3_client=s3_client,
        )
        if settings.data_export_s3_bucket
        else None
    )

    manifest = run_order_contact_email_export(
        request=request,
        reader=SQLAlchemyOrderContactEmailExportReader(
            database_url=settings.required_database_url
        ),
        store=LocalDataExportStore(output_dir=settings.data_export_output_dir),
        publisher=publisher,
    )
    print(
        json.dumps(
            {
                "workload": WORKLOAD_NAME,
                "event": "data_export_succeeded",
                "job_name": DATA_EXPORT_JOB_NAME,
                "timestamp": exported_at.isoformat(),
                **manifest,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return manifest


def main() -> None:
    run_export()


if __name__ == "__main__":
    main()
