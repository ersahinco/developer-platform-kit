from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ci.extract_operator_event import enrich_operator_event
from scripts.ci.extract_operator_event import extract_event
from scripts.ci.extract_operator_event import render_summary


ROOT = Path(__file__).resolve().parents[2]


def test_extract_operational_snapshot_event_selects_latest_matching_run() -> None:
    document = {
        "events": [
            {
                "timestamp": 20,
                "message": json.dumps(
                    {
                        "event": "operational_snapshot_succeeded",
                        "run_id": "github-2",
                        "status": "succeeded",
                    }
                ),
            },
            {
                "timestamp": 10,
                "message": json.dumps(
                    {
                        "event": "operational_snapshot_succeeded",
                        "run_id": "github-1",
                        "status": "succeeded",
                        "orders_count": 1,
                    }
                ),
            },
            {
                "timestamp": 30,
                "message": json.dumps(
                    {
                        "event": "operational_snapshot_succeeded",
                        "run_id": "github-1",
                        "status": "succeeded",
                        "orders_count": 2,
                    }
                ),
            },
        ]
    }

    event = extract_event(
        document,
        event_names={"operational_snapshot_succeeded"},
        run_id="github-1",
    )

    assert event["run_id"] == "github-1"
    assert event["orders_count"] == 2


def test_extract_operational_snapshot_event_rejects_missing_match() -> None:
    with pytest.raises(ValueError, match="no operator event"):
        extract_event(
            {"events": [{"message": "not json"}]},
            event_names={"operational_snapshot_succeeded"},
            run_id="github-1",
        )


def test_operational_snapshot_summary_is_operator_readable() -> None:
    summary = render_summary(
        {
            "run_id": "github-1",
            "status": "succeeded",
            "read_mode": "new",
            "write_mode": "new",
            "orders_count": 2,
            "outbox_pending_count": 0,
        },
        summary_type="operational-snapshot",
    )

    assert "Operational snapshot" in summary
    assert "READ_MODE: new" in summary
    assert "Pending outbox rows: 0" in summary


def test_operator_event_extractor_cli_outputs_json(tmp_path: Path) -> None:
    events_path = tmp_path / "events.json"
    events_path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "timestamp": 1,
                        "message": json.dumps(
                            {
                                "event": "operational_snapshot_succeeded",
                                "run_id": "github-1",
                                "status": "succeeded",
                            }
                        ),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/ci/extract_operator_event.py",
            str(events_path),
            "--event-name",
            "operational_snapshot_succeeded",
            "--run-id",
            "github-1",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert json.loads(completed.stdout)["run_id"] == "github-1"


def test_operator_payload_preserves_required_correlation_keys() -> None:
    enriched = enrich_operator_event(
        {
            "workload": "operational_snapshot_job",
            "event": "operational_snapshot_succeeded",
            "run_id": "github-123",
            "status": "succeeded",
            "timestamp": "2026-06-01T10:00:00+00:00",
        },
        evidence_path="/tmp/operator-evidence/operational-snapshot/operator-event.json",
        image_tag="sha-1234567890abcdef1234567890abcdef12345678",
        task_definition="arn:aws:ecs:task-definition/aws-sdlc-containers:9",
        task_arn="arn:aws:ecs:eu-central-1:123456789012:task/cluster/task-id",
    )

    assert enriched["workload"] == "operational_snapshot_job"
    assert enriched["workload_id"] == "operational_snapshot_job"
    assert enriched["run_id"] == "github-123"
    assert enriched["image_tag"] == "sha-1234567890abcdef1234567890abcdef12345678"
    assert (
        enriched["task_definition"]
        == "arn:aws:ecs:task-definition/aws-sdlc-containers:9"
    )
    assert (
        enriched["task_arn"]
        == "arn:aws:ecs:eu-central-1:123456789012:task/cluster/task-id"
    )
    assert enriched["status"] == "succeeded"
    assert enriched["timestamp"] == "2026-06-01T10:00:00+00:00"
    assert (
        enriched["evidence_path"]
        == "/tmp/operator-evidence/operational-snapshot/operator-event.json"
    )
    assert enriched["correlation"] == {
        "workload_id": "operational_snapshot_job",
        "run_id": "github-123",
        "image_tag": "sha-1234567890abcdef1234567890abcdef12345678",
        "task_definition": "arn:aws:ecs:task-definition/aws-sdlc-containers:9",
        "task_arn": "arn:aws:ecs:eu-central-1:123456789012:task/cluster/task-id",
        "timestamp": "2026-06-01T10:00:00+00:00",
        "status": "succeeded",
    }


def test_operator_event_extractor_accepts_multiple_terminal_events() -> None:
    event = extract_event(
        {
            "events": [
                {
                    "timestamp": 1,
                    "message": json.dumps(
                        {
                            "event": "backfill_paused",
                            "job_name": "order_contact_email_backfill",
                            "message": "backfill paused",
                            "rows_processed": 10,
                        }
                    ),
                }
            ]
        },
        event_names={"backfill_complete", "backfill_paused"},
        run_id=None,
    )

    assert event["event"] == "backfill_paused"
    assert event["rows_processed"] == 10


def test_backfill_summary_is_operator_readable() -> None:
    summary = render_summary(
        {
            "event": "backfill_complete",
            "job_name": "order_contact_email_backfill",
            "message": "backfill complete",
            "rows_processed": 12,
        },
        summary_type="backfill",
    )

    assert "Data backfill event" in summary
    assert "backfill_complete" in summary
    assert "Rows processed: 12" in summary
