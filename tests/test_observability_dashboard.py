import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "docker" / "observability" / "grafana" / "dashboards" / "app-overview.json"


def test_app_overview_dashboard_tracks_readiness_failures() -> None:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    panels = {panel["title"]: panel for panel in dashboard["panels"]}

    readiness = panels["Readiness Failures"]

    assert readiness["type"] == "stat"
    assert readiness["targets"][0]["expr"] == (
        'sum(rate(http_requests_total{route="/ready",status_code=~"5.."}[5m]))'
    )
