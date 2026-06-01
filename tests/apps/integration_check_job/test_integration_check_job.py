from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from integration_check_job.main import parse_targets
from integration_check_job.main import run_checks


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_parse_targets_accepts_comma_list() -> None:
    assert parse_targets("api=http://api:8000/health,https://example.test/ready") == [
        {"name": "api", "url": "http://api:8000/health"},
        {"name": "target-2", "url": "https://example.test/ready"},
    ]


def test_parse_targets_rejects_non_http_targets() -> None:
    with pytest.raises(ValueError, match="must use http or https"):
        parse_targets("file:///tmp/example")


def test_run_checks_writes_evidence_payload(tmp_path: Path) -> None:
    def opener(url: str, timeout: float) -> Any:
        assert url == "http://api.local/health"
        assert timeout == 0.5
        return _Response(200)

    event = run_checks(
        targets="api=http://api.local/health",
        output_dir=str(tmp_path),
        run_id="test-run",
        timeout_seconds=0.5,
        opener=opener,
    )

    assert event["event"] == "integration_check_succeeded"
    assert event["status"] == "succeeded"
    assert event["checked_count"] == 1
    output_path = Path(str(event["output_path"]))
    assert output_path.exists()
    assert json.loads(output_path.read_text())["run_id"] == "test-run"
