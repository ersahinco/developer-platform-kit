from __future__ import annotations

import datetime
import json
from types import SimpleNamespace
from typing import Any

from starlette.responses import Response

import api.main as api_main
import event_consumer.main as event_consumer_main
from application.backfill import BackfillBatchResult
from application.backfill import run_order_contact_email_backfill
from application.operational_snapshot import OperationalSnapshotState
from application.operational_snapshot import build_operational_snapshot
import data_export_job.main as data_export_main
import integration_check_job.main as integration_check_main
import open_dataset_pipeline.main as open_dataset_main
from scripts.ci.extract_operator_event import enrich_operator_event


def _metrics_text(response: Response) -> str:
    return bytes(response.body).decode("utf-8")


def test_service_metrics_expose_workload_identity() -> None:
    metrics = "\n".join(
        [
            _metrics_text(api_main.metrics()),
            _metrics_text(event_consumer_main.metrics()),
        ]
    )

    assert 'workload_info{workload="api",workload_class="edge-service"} 1.0' in metrics
    assert (
        'workload_info{workload="event_consumer",workload_class="internal-service"} 1.0'
        in metrics
    )


def test_service_request_logs_include_workload_event_and_status() -> None:
    request: Any = SimpleNamespace(
        method="GET",
        scope={"route": SimpleNamespace(path="/health")},
        url=SimpleNamespace(path="/health"),
    )

    api_event = api_main._http_request_event(
        request, Response(status_code=200), "request-1", 0.01
    )
    consumer_event = event_consumer_main._http_request_event(
        request, Response(status_code=503), "request-2", 0.01
    )

    assert api_event["workload"] == "api"
    assert api_event["event"] == "http_request"
    assert api_event["status"] == "succeeded"
    assert consumer_event["workload"] == "event_consumer"
    assert consumer_event["event"] == "http_request"
    assert consumer_event["status"] == "failed"


class _CompletedBackfillRepository:
    def process_next_batch(
        self,
        *,
        job_name: str,
        batch_size: int,
    ) -> BackfillBatchResult:
        return BackfillBatchResult(completed=True)


class _SnapshotReader:
    def read(self) -> OperationalSnapshotState:
        return OperationalSnapshotState(
            read_mode="new",
            write_mode="new",
            customers_count=1,
            orders_count=2,
            order_contact_email_count=2,
            outbox_pending_count=0,
            event_receipts_count=4,
        )


def test_job_terminal_events_have_workload_event_status_and_run_id_when_relevant(
    tmp_path,
) -> None:
    backfill_events: list[dict[str, object] | str] = []
    run_order_contact_email_backfill(
        repository=_CompletedBackfillRepository(),
        batch_size=100,
        sleep_seconds=0,
        on_event=backfill_events.append,
    )
    backfill_event = backfill_events[0]
    assert isinstance(backfill_event, dict)
    assert backfill_event["workload"] == "backfill_worker"
    assert backfill_event["event"] == "backfill_complete"
    assert backfill_event["status"] == "succeeded"
    assert backfill_event["mode"] == "checkpointed"
    assert "timestamp" in backfill_event

    snapshot_event = build_operational_snapshot(
        reader=_SnapshotReader(),
        run_id="snapshot-run",
        captured_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    ).as_event()
    assert snapshot_event["workload"] == "operational_snapshot_job"
    assert snapshot_event["run_id"] == "snapshot-run"
    assert snapshot_event["status"] == "succeeded"
    assert snapshot_event["mode"] == "read_only"
    assert "timestamp" in snapshot_event

    class _Response:
        status = 200

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    integration_event = integration_check_main.run_checks(
        targets="api=http://api.local/health",
        output_dir=str(tmp_path),
        run_id="integration-run",
        timeout_seconds=0.5,
        opener=lambda _url, timeout: _Response(),
    )
    assert integration_event["workload"] == "integration_check_job"
    assert integration_event["run_id"] == "integration-run"
    assert integration_event["status"] == "succeeded"
    assert integration_event["mode"] == "http_check"
    assert "timestamp" in integration_event
    assert integration_event["evidence_path"] == integration_event["output_path"]


def test_export_job_events_include_workload_identity_and_terminal_status(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.setattr(data_export_main.settings, "database_url", "postgresql://db")
    monkeypatch.setattr(
        data_export_main.settings, "data_export_output_dir", str(tmp_path)
    )
    monkeypatch.setattr(data_export_main.settings, "data_export_run_id", "export-run")
    monkeypatch.setattr(data_export_main.settings, "data_export_date", "2026-01-01")
    monkeypatch.setattr(
        data_export_main, "S3DataExportPublisher", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        data_export_main,
        "SQLAlchemyOrderContactEmailExportReader",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        data_export_main, "LocalDataExportStore", lambda **_kwargs: object()
    )
    monkeypatch.setattr(
        data_export_main,
        "run_order_contact_email_export",
        lambda **_kwargs: {"run_id": "export-run", "status": "succeeded"},
    )

    data_export_main.run_export()
    export_event = json.loads(capsys.readouterr().out)

    assert export_event["workload"] == "data_export_job"
    assert export_event["run_id"] == "export-run"
    assert export_event["status"] == "succeeded"
    assert "timestamp" in export_event


def test_open_dataset_pipeline_event_includes_workload_identity(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.setattr(open_dataset_main.settings, "open_dataset_name", "example")
    monkeypatch.setattr(
        open_dataset_main.settings, "open_dataset_url", "https://example.test/data.csv"
    )
    monkeypatch.setattr(
        open_dataset_main.settings, "open_dataset_output_dir", str(tmp_path)
    )
    monkeypatch.setattr(
        open_dataset_main.settings, "open_dataset_run_id", "dataset-run"
    )
    monkeypatch.setattr(open_dataset_main.settings, "open_dataset_date", "2026-01-01")
    monkeypatch.setattr(open_dataset_main, "OpenDatasetLoader", lambda: object())
    monkeypatch.setattr(
        open_dataset_main, "DuckDBOpenDatasetStore", lambda **_kwargs: object()
    )
    monkeypatch.setattr(
        open_dataset_main,
        "run_open_dataset_pipeline",
        lambda **_kwargs: {"run_id": "dataset-run", "status": "succeeded"},
    )

    open_dataset_main.run_pipeline()
    event = json.loads(capsys.readouterr().out)

    assert event["workload"] == "open_dataset_pipeline"
    assert event["run_id"] == "dataset-run"
    assert event["status"] == "succeeded"
    assert "timestamp" in event


def test_operator_payload_events_include_artifact_context() -> None:
    event = enrich_operator_event(
        {
            "workload": "operational_snapshot_job",
            "event": "operational_snapshot_succeeded",
            "run_id": "github-run",
            "mode": "read_only",
            "status": "succeeded",
            "captured_at": "2026-01-01T00:00:00+00:00",
        },
        evidence_path="/tmp/operator-evidence/operational-snapshot/operator-event.json",
    )

    assert event["workload"] == "operational_snapshot_job"
    assert event["run_id"] == "github-run"
    assert event["mode"] == "read_only"
    assert event["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert event["status"] == "succeeded"
    assert (
        event["evidence_path"]
        == "/tmp/operator-evidence/operational-snapshot/operator-event.json"
    )
