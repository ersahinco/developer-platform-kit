from __future__ import annotations

from prometheus_client import Gauge


_WORKLOAD_INFO: Gauge | None = None


def ensure_workload_info_metric(*, workload: str, workload_class: str) -> None:
    """Expose stable workload identity once per process."""
    global _WORKLOAD_INFO
    if _WORKLOAD_INFO is None:
        _WORKLOAD_INFO = Gauge(
            "workload_info",
            "Static workload identity and operational class.",
            ["workload", "workload_class"],
        )
    _WORKLOAD_INFO.labels(workload=workload, workload_class=workload_class).set(1)
