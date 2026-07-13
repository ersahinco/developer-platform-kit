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
import churn_model_train_job.main as churn_train_main
import churn_prediction_api.main as churn_prediction_main
import foreign_inventory_sync.main as foreign_inventory_sync_main
import integration_check_job.main as integration_check_main
import lake_orders_ingest_job.main as lake_orders_ingest_main
import open_dataset_pipeline.main as open_dataset_main
from support_triage_llm.evidence import failed_operator_payload
import support_triage_llm.main as support_triage_main
from scripts.ci.extract_operator_event import enrich_operator_event

from ._helpers import load_json


SERVICE_METRICS = {
    "api": api_main.metrics,
    "churn_prediction_api": churn_prediction_main.metrics,
    "event_consumer": event_consumer_main.metrics,
    "foreign_inventory_sync": foreign_inventory_sync_main.metrics,
    "support_triage_llm": support_triage_main.metrics,
}
SERVICE_REQUEST_EVENTS = {
    "api": api_main._http_request_event,
    "churn_prediction_api": churn_prediction_main._http_request_event,
    "event_consumer": event_consumer_main._http_request_event,
    "foreign_inventory_sync": foreign_inventory_sync_main._http_request_event,
    "support_triage_llm": support_triage_main._http_request_event,
}


def _metrics_text(response: Response) -> str:
    return bytes(response.body).decode("utf-8")


def test_service_metrics_expose_workload_identity() -> None:
    service_workloads = [
        workload
        for workload in load_json("platform/workloads.json")["workloads"]
        if workload["kind"] == "service"
    ]
    missing_modules = [
        workload["name"]
        for workload in service_workloads
        if workload["name"] not in SERVICE_METRICS
    ]
    assert missing_modules == []
    metrics = "\n".join(
        _metrics_text(SERVICE_METRICS[workload["name"]]())
        for workload in service_workloads
    )

    for workload in service_workloads:
        workload_class = workload["operational"]["class"]
        assert (
            f'workload_info{{workload="{workload["name"]}",'
            f'workload_class="{workload_class}"}} 1.0'
        ) in metrics


def test_service_request_logs_include_workload_event_and_status() -> None:
    service_workloads = [
        workload
        for workload in load_json("platform/workloads.json")["workloads"]
        if workload["kind"] == "service"
    ]
    missing_modules = [
        workload["name"]
        for workload in service_workloads
        if workload["name"] not in SERVICE_REQUEST_EVENTS
    ]
    assert missing_modules == []

    request: Any = SimpleNamespace(
        method="GET",
        scope={"route": SimpleNamespace(path="/health")},
        url=SimpleNamespace(path="/health"),
    )

    for workload in service_workloads:
        event_builder = SERVICE_REQUEST_EVENTS[workload["name"]]
        success_event = event_builder(
            request, Response(status_code=200), "request-1", 0.01
        )
        failure_event = event_builder(
            request, Response(status_code=503), "request-2", 0.01
        )

        assert success_event["workload"] == workload["name"]
        assert success_event["event"] == "http_request"
        assert success_event["request_id"] == "request-1"
        assert success_event["status"] == "succeeded"
        assert success_event["status_code"] == 200
        assert failure_event["workload"] == workload["name"]
        assert failure_event["event"] == "http_request"
        assert failure_event["request_id"] == "request-2"
        assert failure_event["status"] == "failed"
        assert failure_event["status_code"] == 503


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

    class _Loader:
        def load_bytes(self, source_url: str) -> bytes:
            assert source_url == "https://example.test/data.csv"
            return b"example"

    class _Store:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def persist(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["raw_bytes"] == b"example"
            return {"run_id": "dataset-run", "status": "succeeded"}

    monkeypatch.setattr(open_dataset_main, "OpenDatasetLoader", _Loader)
    monkeypatch.setattr(open_dataset_main, "DuckDBOpenDatasetStore", _Store)

    open_dataset_main.run_pipeline()
    event = json.loads(capsys.readouterr().out)

    assert event["workload"] == "open_dataset_pipeline"
    assert event["run_id"] == "dataset-run"
    assert event["status"] == "succeeded"
    assert "timestamp" in event


def test_lake_orders_ingest_event_includes_run_evidence(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.setattr(
        lake_orders_ingest_main.settings,
        "lake_orders_source_dir",
        str(tmp_path / "source"),
    )
    monkeypatch.setattr(
        lake_orders_ingest_main.settings,
        "lake_orders_output_dir",
        str(tmp_path),
    )
    monkeypatch.setattr(
        lake_orders_ingest_main.settings,
        "lake_orders_run_id",
        "lake-run",
    )
    monkeypatch.setattr(
        lake_orders_ingest_main.settings,
        "lake_orders_ingest_date",
        "2026-05-13",
    )
    monkeypatch.setattr(
        lake_orders_ingest_main,
        "run_lake_orders_ingest",
        lambda **_kwargs: {
            "dataset": "lake_orders",
            "run_id": "lake-run",
            "status": "succeeded",
            "row_count": 4,
            "late_arrival_count": 1,
            "parquet_object_count": 2,
            "evidence_paths": [
                "raw/lake_orders/dt=2026-05-13/lake-run.parquet",
                "curated/lake_orders/dt=2026-05-13/lake-run.parquet",
                "manifests/lake_orders/dt=2026-05-13/lake-run.json",
            ],
        },
    )

    lake_orders_ingest_main.run_ingest()
    event = json.loads(capsys.readouterr().out)

    assert event["workload"] == "lake_orders_ingest_job"
    assert event["event"] == "lake_orders_ingest_succeeded"
    assert event["run_id"] == "lake-run"
    assert event["status"] == "succeeded"
    assert event["row_count"] == 4
    assert event["late_arrival_count"] == 1
    assert event["parquet_object_count"] == 2
    assert event["evidence_paths"]
    assert "timestamp" in event


def test_churn_model_train_event_includes_model_evidence(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.setattr(
        churn_train_main.settings,
        "churn_training_data_path",
        str(tmp_path / "training.csv"),
    )
    monkeypatch.setattr(
        churn_train_main.settings,
        "churn_model_output_dir",
        str(tmp_path),
    )
    monkeypatch.setattr(churn_train_main.settings, "churn_model_run_id", "train-run")
    monkeypatch.setattr(
        churn_train_main.settings,
        "churn_model_train_date",
        "2026-05-13",
    )
    monkeypatch.setattr(
        churn_train_main,
        "train_churn_model",
        lambda _request: {
            "dataset": "customer_churn",
            "run_id": "train-run",
            "model_version": "model-v1",
            "status": "succeeded",
            "training_row_count": 8,
            "metrics": {"accuracy": 0.875},
            "drift_summary": {"status": "ok"},
            "evidence_paths": [
                "models/churn_prediction/dt=2026-05-13/train-run.json",
                "manifests/churn_prediction/dt=2026-05-13/train-run.json",
            ],
        },
    )

    churn_train_main.run_training()
    event = json.loads(capsys.readouterr().out)

    assert event["workload"] == "churn_model_train_job"
    assert event["event"] == "churn_model_train_succeeded"
    assert event["run_id"] == "train-run"
    assert event["model_version"] == "model-v1"
    assert event["status"] == "succeeded"
    assert event["training_row_count"] == 8
    assert event["metrics"]["accuracy"] == 0.875
    assert event["drift_summary"]["status"] == "ok"
    assert event["evidence_paths"]
    assert "timestamp" in event


def test_churn_prediction_event_includes_model_correlation(capsys) -> None:
    class _State:
        churn_model = {
            "model_version": "model-v1",
            "run_id": "train-run",
            "weights": {
                "tenure_months": -0.05,
                "monthly_charges": 0.01,
                "support_tickets_90d": 0.5,
                "late_payments_12m": 0.6,
                "usage_drop_pct": 0.04,
            },
            "intercept": 0.0,
            "threshold": 0.5,
        }

    request: Any = SimpleNamespace(app=SimpleNamespace(state=_State))
    payload = churn_prediction_main.PredictionRequest(
        customer_id="C-test",
        tenure_months=6,
        monthly_charges=112.0,
        support_tickets_90d=4,
        late_payments_12m=3,
        usage_drop_pct=58,
    )

    result = churn_prediction_main.predict(payload, request)
    event = json.loads(capsys.readouterr().out)

    assert isinstance(result, dict)
    assert result["status"] == "succeeded"
    assert result["model_version"] == "model-v1"
    assert result["run_id"] == "train-run"
    assert event["workload"] == "churn_prediction_api"
    assert event["event"] == "churn_prediction"
    assert event["model_version"] == "model-v1"
    assert event["run_id"] == "train-run"
    assert event["status"] == "succeeded"


def test_support_triage_event_includes_prompt_token_cost_and_run_correlation(
    tmp_path,
    capsys,
) -> None:
    prompt = {
        "prompt_version": "support-triage-v1",
        "prompt_sha256": "prompt-sha",
        "prompt_text": "version: support-triage-v1\nClassify support tickets.",
    }

    _State = SimpleNamespace(output_dir=tmp_path, prompt=prompt)

    request: Any = SimpleNamespace(app=SimpleNamespace(state=_State))
    payload = support_triage_main.TriageRequest(
        ticket_id="T-test",
        subject="Production API is down",
        body="Checkout is unavailable.",
        customer_tier="enterprise",
        run_id="triage-run",
    )

    result = support_triage_main.triage(payload, request)
    assert isinstance(result, dict)
    token_evidence = result["token_evidence"]
    assert isinstance(token_evidence, dict)
    input_tokens = token_evidence["input_tokens"]
    assert isinstance(input_tokens, int)
    estimated_cost_usd = result["estimated_cost_usd"]
    assert isinstance(estimated_cost_usd, float)
    event = json.loads(capsys.readouterr().out)

    assert result["workload"] == "support_triage_llm"
    assert result["event"] == "support_triage_completed"
    assert result["run_id"] == "triage-run"
    assert result["prompt_version"] == "support-triage-v1"
    assert input_tokens > 0
    assert estimated_cost_usd > 0
    assert result["evidence_path"]
    assert event["workload"] == "support_triage_llm"
    assert event["run_id"] == "triage-run"
    assert event["prompt_version"] == "support-triage-v1"


def test_support_triage_failed_run_operator_payload_is_self_contained(tmp_path) -> None:
    payload = failed_operator_payload(
        output_dir=tmp_path,
        run_id="failed-run",
        reason="prompt missing",
    )

    assert payload["workload"] == "support_triage_llm"
    assert payload["event"] == "support_triage_failed"
    assert payload["status"] == "failed"
    assert payload["mode"] == "operator_payload"
    assert payload["run_id"] == "failed-run"
    evidence = json.loads((tmp_path / payload["evidence_path"]).read_text())
    assert evidence["evidence_path"] == payload["evidence_path"]


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
