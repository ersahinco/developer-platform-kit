from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LOCAL_KUBERNETES_ROOT = ROOT / "infra" / "local-kubernetes"
DEFAULT_NAMESPACE = "aws-sdlc-local"
DEFAULT_OUTPUT_DIR = Path("/tmp/aws-sdlc-containers-local-kubernetes-evidence")
API_METRIC_NEEDLE = 'workload_info{workload="api"'
EVENT_CONSUMER_METRIC_NEEDLE = 'workload_info{workload="event_consumer"'
EVENT_CONSUMED_NEEDLE = '"event": "event_consumed"'
