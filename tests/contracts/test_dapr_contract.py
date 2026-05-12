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


def test_order_events_sns_topic_is_encrypted() -> None:
    encryption = _read("infra/app/encryption.tf")
    messaging = _read("infra/app/messaging.tf")
    workload_jobs = _read("infra/app/workload_jobs.tf")

    assert 'resource "aws_kms_key" "order_events_sns"' in encryption
    assert "kms:EncryptionContext:aws:sns:topicArn" in encryption
    assert "kms_master_key_id" in messaging
    assert "aws_kms_key.order_events_sns.arn" in messaging
    assert "UseOrderEventsSnsKms" in workload_jobs
    assert "kms:ViaService" in workload_jobs


def test_order_events_queue_name_is_preserved_for_dapr_adoption() -> None:
    messaging = _read("infra/app/messaging.tf")
    local_pubsub = _read("dapr/local/components/order-events-pubsub.yaml")
    runbook = _read("docs/runbooks/order-event-queue-failure.md")
    queue_docs = "\n".join([messaging, local_pubsub, runbook])

    assert "${local.name}-order-events.fifo" in messaging
    assert "aws-sdlc-containers-order-events.fifo" in local_pubsub
    assert "aws-sdlc-containers-order-events-dlq.fifo" in local_pubsub
    assert "aws-sdlc-containers-order-events.fifo" in runbook
    assert "order-event-consumer.fifo" not in queue_docs
    assert "order-event-consumer-dlq.fifo" not in queue_docs


def test_app_build_validates_dapr_and_local_runtime_changes() -> None:
    app_build = _read(".github/workflows/app-build.yml")

    assert app_build.count('- "compose.yaml"') == 2
    assert app_build.count('- "dapr/**"') == 2


def test_dapr_portability_contract_keeps_broker_at_runtime_edge() -> None:
    contract = _read("docs/dapr-portability-contract.md").lower()
    consumer = _read("apps/order_event_consumer/main.py").lower()
    adapter = _read("packages/infrastructure/dapr/pubsub.py").lower()
    runtime_edge = "\n".join(
        [
            _read("infra/app/messaging.tf"),
            _read("dapr/local/components/order-events-pubsub.yaml"),
        ]
    ).lower()

    for phrase in [
        "dapr pub/sub",
        "cloudevents",
        "outbox",
        "sns/sqs",
        "redis",
        "kafka",
        "azure service bus",
        "gcp pub/sub",
        "provider-native sqs metrics",
    ]:
        assert phrase in contract

    assert "/v1.0/publish/" in adapter
    assert "sns" not in consumer
    assert "sqs" not in consumer
    assert "boto3" not in consumer
    assert "snssqs" in runtime_edge
