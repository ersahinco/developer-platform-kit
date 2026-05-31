from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ci.extract_operational_snapshot_event import extract_event
from scripts.ci.extract_operational_snapshot_event import render_summary


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

    event = extract_event(document, run_id="github-1")

    assert event["run_id"] == "github-1"
    assert event["orders_count"] == 2


def test_extract_operational_snapshot_event_rejects_missing_match() -> None:
    with pytest.raises(ValueError, match="no operational_snapshot_succeeded"):
        extract_event({"events": [{"message": "not json"}]}, run_id="github-1")


def test_operational_snapshot_summary_is_operator_readable() -> None:
    summary = render_summary(
        {
            "run_id": "github-1",
            "status": "succeeded",
            "read_mode": "new",
            "write_mode": "new",
            "orders_count": 2,
            "outbox_pending_count": 0,
        }
    )

    assert "Operational snapshot" in summary
    assert "READ_MODE: new" in summary
    assert "Pending outbox rows: 0" in summary


def test_operational_snapshot_extractor_cli_outputs_json(tmp_path: Path) -> None:
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
            "scripts/ci/extract_operational_snapshot_event.py",
            str(events_path),
            "--run-id",
            "github-1",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert json.loads(completed.stdout)["run_id"] == "github-1"
