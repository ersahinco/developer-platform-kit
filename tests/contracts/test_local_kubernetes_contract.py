from __future__ import annotations

from typing import Any

import yaml

from ._helpers import ROOT, load_json


LOCAL_KUBERNETES_ROOT = ROOT / "infra" / "local-kubernetes"
LOCAL_KUBERNETES_WORKLOADS = {
    "api": "api",
    "event_consumer": "event-consumer",
    "backfill_worker": "backfill-worker",
    "data_export_job": "data-export-job",
    "operational_snapshot_job": "operational-snapshot-job",
    "integration_check_job": "integration-check-job",
}


def _documents() -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in sorted(LOCAL_KUBERNETES_ROOT.glob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if isinstance(document, dict):
                documents.append(document)
    return documents


def _by_kind_name() -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (document["kind"], document["metadata"]["name"]): document
        for document in _documents()
        if isinstance(document.get("metadata"), dict)
    }


def _workloads() -> dict[str, dict[str, Any]]:
    return {
        workload["name"]: workload
        for workload in load_json("platform/workloads.json")["workloads"]
    }


def _config_names(workload: dict[str, Any]) -> set[str]:
    config = workload["config"]
    return set(config["env"]) | set(config["secrets"])


def test_local_kubernetes_supported_workloads_are_intentional() -> None:
    workloads = _workloads()
    supported = {
        name
        for name, workload in workloads.items()
        if "local-kubernetes" in workload["runtime"]["supported"]
    }

    assert supported == set(LOCAL_KUBERNETES_WORKLOADS)
    for name in supported:
        assert "local-kubernetes" not in workloads[name]["runtime"]["admitted"]


def test_local_kubernetes_kustomization_is_static_and_small() -> None:
    kustomization = yaml.safe_load(
        (LOCAL_KUBERNETES_ROOT / "kustomization.yaml").read_text(encoding="utf-8")
    )

    assert kustomization["kind"] == "Kustomization"
    assert set(kustomization["resources"]) == {
        "namespace.yaml",
        "runtime-db.yaml",
        "runtime-eventing.yaml",
        "workload-services.yaml",
        "workload-jobs.yaml",
    }
    assert not (LOCAL_KUBERNETES_ROOT / "Chart.yaml").exists()


def test_local_kubernetes_manifests_match_workload_contract() -> None:
    workloads = _workloads()
    documents = _by_kind_name()
    config_map = documents[("ConfigMap", "workload-config")]
    secret = documents[("Secret", "workload-secrets")]
    config_names = set(config_map["data"])
    secret_names = set(secret["stringData"])

    api = workloads["api"]
    api_deployment = documents[("Deployment", "api")]
    api_service = documents[("Service", "api")]
    api_container = api_deployment["spec"]["template"]["spec"]["containers"][0]

    assert api_container["image"] == "aws-sdlc-containers-api:local-kubernetes"
    assert api_container["ports"][0]["containerPort"] == api["service"]["port"]
    assert api_service["spec"]["ports"][0]["port"] == api["service"]["port"]
    assert api_container["readinessProbe"]["httpGet"]["path"] == "/ready"
    assert api_container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert api_deployment["metadata"]["annotations"]["workload.metrics.path"] == (
        "/metrics"
    )
    assert _config_names(api).issubset(config_names | secret_names)

    for workload_name, manifest_name in LOCAL_KUBERNETES_WORKLOADS.items():
        workload = workloads[workload_name]
        if workload["kind"] != "job":
            continue
        job = documents[("Job", manifest_name)]
        container = job["spec"]["template"]["spec"]["containers"][0]
        assert container["image"].endswith(":local-kubernetes")
        assert (
            job["spec"]["template"]["metadata"]["labels"]["workload"] == workload_name
        )
        assert _config_names(workload).issubset(config_names | secret_names)

    data_export_job = documents[("Job", "data-export-job")]
    init_names = {
        container["name"]
        for container in data_export_job["spec"]["template"]["spec"]["initContainers"]
    }
    assert {"wait-for-pgbouncer", "wait-for-schema"}.issubset(init_names)

    event_consumer = workloads["event_consumer"]
    event_deployment = documents[("Deployment", "event-consumer")]
    event_service = documents[("Service", "event-consumer")]
    event_pod_spec = event_deployment["spec"]["template"]["spec"]
    event_containers = {
        container["name"]: container for container in event_pod_spec["containers"]
    }
    event_app = event_containers["event-consumer"]
    daprd = event_containers["daprd"]

    assert event_app["image"] == ("aws-sdlc-containers-event-consumer:local-kubernetes")
    assert event_app["ports"][0]["containerPort"] == event_consumer["service"]["port"]
    assert (
        event_service["spec"]["ports"][0]["port"] == event_consumer["service"]["port"]
    )
    assert event_app["readinessProbe"]["httpGet"]["path"] == "/ready"
    assert event_app["livenessProbe"]["httpGet"]["path"] == "/health"
    assert "--resources-path" in daprd["args"]
    assert "--config" in daprd["args"]
    assert documents[("ConfigMap", "dapr-components")]["data"][
        "async-events-pubsub.yaml"
    ]
    assert documents[("ConfigMap", "dapr-config")]["data"]["config.yaml"]
    assert ("Deployment", "redis") in documents
    assert ("Service", "redis") in documents


def test_local_kubernetes_runtime_proves_identity_network_and_storage() -> None:
    documents = _by_kind_name()
    config_map = documents[("ConfigMap", "workload-config")]

    assert ("ServiceAccount", "workload-runtime") in documents
    assert ("PersistentVolumeClaim", "data-exports") in documents
    assert ("Service", "db") in documents
    assert ("Service", "pgbouncer") in documents
    assert ("Service", "redis") in documents
    assert ("Job", "liquibase") in documents
    assert ("Job", "backfill-worker") in documents
    assert ("Job", "operational-snapshot-job") in documents
    assert config_map["data"]["DATA_EXPORT_OUTPUT_DIR"] == "/exports"
    assert config_map["data"]["DATA_EXPORT_S3_BUCKET"] == ""
    assert config_map["data"]["DAPR_PUBSUB_NAME"] == "async-events-pubsub"
    assert config_map["data"]["DAPR_TOPIC"] == "async-events-v1.fifo"

    for document in _documents():
        metadata = document.get("metadata", {})
        labels = metadata.get("labels", {}) if isinstance(metadata, dict) else {}
        if labels:
            assert labels.get("runtime.target") == "local-kubernetes"
