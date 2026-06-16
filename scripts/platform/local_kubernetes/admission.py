from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import json
from typing import Any

import yaml

from scripts.platform.local_kubernetes.constants import LOCAL_KUBERNETES_ROOT
from scripts.platform.local_kubernetes.constants import ROOT


@dataclass(frozen=True)
class AdmissionRow:
    workload: str
    kind: str
    status: str
    supported: bool
    manifest: str
    checks: list[str]
    blockers: list[str]


@dataclass(frozen=True)
class ManifestFacts:
    kind: str
    name: str
    workload: str | None = None
    config_keys: frozenset[str] = field(default_factory=frozenset)
    secret_keys: frozenset[str] = field(default_factory=frozenset)
    container_names: tuple[str, ...] = ()
    readiness_paths: frozenset[str] = field(default_factory=frozenset)
    liveness_paths: frozenset[str] = field(default_factory=frozenset)
    restart_policy: str | None = None
    has_backoff_limit: bool = False


def _load_json(path: str) -> dict[str, Any]:
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _manifests() -> list[ManifestFacts]:
    manifests: list[ManifestFacts] = []
    for path in sorted(LOCAL_KUBERNETES_ROOT.glob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            manifest = _manifest_from_document(document)
            if manifest is not None:
                manifests.append(manifest)
    return manifests


def _manifest_from_document(document: Any) -> ManifestFacts | None:
    if not isinstance(document, dict):
        return None

    kind = document.get("kind")
    metadata = _mapping(document.get("metadata"))
    name = metadata.get("name")
    if not isinstance(kind, str) or not isinstance(name, str):
        return None

    spec = _mapping(document.get("spec"))
    pod_metadata = _pod_template_metadata(spec)
    pod_spec = _pod_template_spec(spec)

    return ManifestFacts(
        kind=kind,
        name=name,
        workload=_workload_label(pod_metadata),
        config_keys=(
            _mapping_keys(document.get("data")) if kind == "ConfigMap" else frozenset()
        ),
        secret_keys=(
            _mapping_keys(document.get("stringData"))
            if kind == "Secret"
            else frozenset()
        ),
        container_names=_container_names(pod_spec),
        readiness_paths=_probe_paths(pod_spec, "readinessProbe"),
        liveness_paths=_probe_paths(pod_spec, "livenessProbe"),
        restart_policy=_string_or_none(pod_spec.get("restartPolicy")),
        has_backoff_limit="backoffLimit" in spec,
    )


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _pod_template_metadata(spec: dict[str, Any]) -> dict[str, Any]:
    template = _mapping(spec.get("template"))
    return _mapping(template.get("metadata"))


def _pod_template_spec(spec: dict[str, Any]) -> dict[str, Any]:
    template = _mapping(spec.get("template"))
    return _mapping(template.get("spec"))


def _workload_label(pod_metadata: dict[str, Any]) -> str | None:
    labels = _mapping(pod_metadata.get("labels"))
    return _string_or_none(labels.get("workload"))


def _mapping_keys(value: Any) -> frozenset[str]:
    if not isinstance(value, dict):
        return frozenset()
    return frozenset(key for key in value if isinstance(key, str))


def _containers(pod_spec: dict[str, Any]) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = []
    for section in ("initContainers", "containers"):
        section_value = pod_spec.get(section)
        if isinstance(section_value, list):
            containers.extend(item for item in section_value if isinstance(item, dict))
    return containers


def _container_names(pod_spec: dict[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    for container in _containers(pod_spec):
        name = container.get("name")
        if isinstance(name, str):
            names.append(name)
    return tuple(names)


def _probe_paths(pod_spec: dict[str, Any], probe: str) -> frozenset[str]:
    paths: set[str] = set()
    for container in _containers(pod_spec):
        http_get = _mapping(_mapping(container.get(probe)).get("httpGet"))
        path = http_get.get("path")
        if isinstance(path, str):
            paths.add(path)
    return frozenset(paths)


def _manifest_by_kind_name(
    manifests: list[ManifestFacts],
) -> dict[tuple[str, str], ManifestFacts]:
    return {(manifest.kind, manifest.name): manifest for manifest in manifests}


def _workload_manifest(
    workload: dict[str, Any],
    manifests: list[ManifestFacts],
) -> ManifestFacts | None:
    expected_kind = "Deployment" if workload["kind"] == "service" else "Job"
    for manifest in manifests:
        if manifest.kind == expected_kind and manifest.workload == workload["name"]:
            return manifest
    return None


def _config_names(workload: dict[str, Any]) -> set[str]:
    config = workload["config"]
    return set(config["env"]) | set(config["secrets"])


def admission_rows() -> list[AdmissionRow]:
    workloads = _load_json("platform/workloads.json")["workloads"]
    manifests = _manifests()
    manifests_by_kind_name = _manifest_by_kind_name(manifests)
    config_map = manifests_by_kind_name.get(("ConfigMap", "workload-config"))
    secret = manifests_by_kind_name.get(("Secret", "workload-secrets"))
    available_config = (config_map.config_keys if config_map else frozenset()) | (
        secret.secret_keys if secret else frozenset()
    )
    rows: list[AdmissionRow] = []

    for workload in workloads:
        supported = "local-kubernetes" in workload["runtime"]["supported"]
        manifest = _workload_manifest(workload, manifests)
        checks: list[str] = []
        blockers: list[str] = []

        if not supported:
            blockers.append("runtime.supported does not include local-kubernetes")
        if manifest is None:
            blockers.append("no local Kubernetes Deployment/Job manifest")
            manifest_name = ""
        else:
            manifest_name = f"{manifest.kind}/{manifest.name}"
            checks.append(manifest_name)

        if supported or manifest is not None:
            missing_config = sorted(_config_names(workload) - available_config)
            if missing_config:
                blockers.append(
                    "missing local config or secret names: " + ", ".join(missing_config)
                )
            elif supported:
                checks.append("config and secret names are injectable")

            if workload["kind"] == "service":
                service = (
                    manifests_by_kind_name.get(("Service", manifest.name))
                    if manifest
                    else None
                )
                if service is None:
                    blockers.append("no matching local Kubernetes Service")
                elif supported:
                    checks.append(f"Service/{service.name}")
                if manifest is None or "/ready" not in manifest.readiness_paths:
                    blockers.append("service lacks /ready readinessProbe")
                if manifest is None or "/health" not in manifest.liveness_paths:
                    blockers.append("service lacks /health livenessProbe")
                if manifest and supported:
                    checks.append("health and readiness probes")
            else:
                if manifest is None or manifest.restart_policy != "Never":
                    blockers.append("job restartPolicy must be Never")
                if manifest is None or not manifest.has_backoff_limit:
                    blockers.append("job backoffLimit is not explicit")
                if supported and manifest and manifest.restart_policy == "Never":
                    checks.append("bounded job execution")

        if workload.get("dapr"):
            if not _has_local_dapr_eventing(manifests_by_kind_name, manifest):
                blockers.append("local Kubernetes Dapr/eventing proof is not present")
            elif supported:
                checks.append("Dapr pub/sub sidecar and Redis proof path")

        status = "ready" if supported and not blockers else "not-ready"
        rows.append(
            AdmissionRow(
                workload=workload["name"],
                kind=workload["kind"],
                status=status,
                supported=supported,
                manifest=manifest_name,
                checks=checks,
                blockers=blockers,
            )
        )
    return rows


def _has_local_dapr_eventing(
    manifests: dict[tuple[str, str], ManifestFacts],
    manifest: ManifestFacts | None,
) -> bool:
    if manifest is None:
        return False
    return (
        "event-consumer" in manifest.container_names
        and "daprd" in manifest.container_names
        and ("ConfigMap", "dapr-components") in manifests
        and ("ConfigMap", "dapr-config") in manifests
        and ("Deployment", "redis") in manifests
        and ("Service", "redis") in manifests
    )
