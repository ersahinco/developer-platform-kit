from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_order_events_dapr_resiliency_is_bounded_and_component_scoped() -> None:
    local_resiliency = _read("dapr/local/components/resiliency.yaml")
    template_resiliency = _read("infra/app/templates/dapr/resiliency.yaml.tftpl")

    for spec in [local_resiliency, template_resiliency]:
        assert "kind: Resiliency" in spec
        assert "order-event-consumer" in spec
        assert "order-events-pubsub:" in spec
        assert "outbound:" in spec
        assert "inbound:" in spec
        assert "maxRetries: 2" in spec
        assert "orderEventsPubsub: 10s" in spec
        assert "trip: consecutiveFailures > 5" in spec
        assert "maxRetries: -1" not in spec


def test_order_events_ecs_sidecar_loads_resiliency_spec() -> None:
    messaging = _read("infra/app/messaging.tf")
    workload_jobs = _read("infra/app/workload_jobs.tf")
    compose = _read("compose.yaml")

    assert 'aws_s3_object" "order_events_dapr_resiliency' in messaging
    assert "templates/dapr/resiliency.yaml.tftpl" in messaging
    assert "/dapr/components/resiliency.yaml" in workload_jobs
    assert "--components-path" in workload_jobs
    assert "./dapr/local/components:/components:ro" in compose


def test_app_build_validates_dapr_and_local_runtime_changes() -> None:
    app_build = _read(".github/workflows/app-build.yml")

    assert app_build.count('- "compose.yaml"') == 2
    assert app_build.count('- "dapr/**"') == 2
