from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from starlette.responses import Response

import foreign_inventory_sync.main as foreign_main


def test_health_metrics_and_request_event_shape() -> None:
    health = foreign_main.health()
    metrics = foreign_main.metrics()
    request: Any = SimpleNamespace(
        method="GET",
        scope={"route": SimpleNamespace(path="/health")},
        url=SimpleNamespace(path="/health"),
    )

    event = foreign_main._http_request_event(
        request,
        Response(status_code=200),
        "request-1",
        0.01,
    )

    assert health["status"] == "ok"
    assert b'workload_info{workload="foreign_inventory_sync"' in metrics.body
    assert event["workload"] == "foreign_inventory_sync"
    assert event["event"] == "http_request"
    assert event["request_id"] == "request-1"
    assert event["route"] == "/health"
    assert event["status_code"] == 200
