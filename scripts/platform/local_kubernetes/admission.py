from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
import json
import re
from typing import Any

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
        for text in _manifest_texts(path.read_text(encoding="utf-8")):
            manifest = _manifest_from_text(text)
            if manifest is not None:
                manifests.append(manifest)
    return manifests


def _manifest_texts(text: str) -> Iterable[str]:
    for section in re.split(r"^---\s*$", text, flags=re.MULTILINE):
        if section.strip():
            yield section


def _manifest_from_text(text: str) -> ManifestFacts | None:
    kind = _value_at_indent(text, "kind", indent=0)
    name = _metadata_name(text)
    if kind is None or name is None:
        return None

    return ManifestFacts(
        kind=kind,
        name=name,
        workload=_indented_value(text, "workload"),
        config_keys=_mapping_keys(text, "data") if kind == "ConfigMap" else frozenset(),
        secret_keys=(
            _mapping_keys(text, "stringData") if kind == "Secret" else frozenset()
        ),
        container_names=tuple(_list_item_names(text)),
        readiness_paths=_probe_paths(text, "readinessProbe"),
        liveness_paths=_probe_paths(text, "livenessProbe"),
        restart_policy=_indented_value(text, "restartPolicy"),
        has_backoff_limit=_indented_value(text, "backoffLimit") is not None,
    )


def _indented_value(text: str, key: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if line.startswith(" ") and stripped.startswith(f"{key}:"):
            return stripped.split(":", 1)[1].strip()
    return None


def _value_at_indent(text: str, key: str, *, indent: int) -> str | None:
    prefix = " " * indent + f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None


def _metadata_name(text: str) -> str | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line == "metadata:":
            for metadata_line in lines[index + 1 :]:
                if metadata_line and not metadata_line.startswith(" "):
                    return None
                if metadata_line.startswith("  name:"):
                    return metadata_line.split(":", 1)[1].strip()
    return None


def _mapping_keys(text: str, section: str) -> frozenset[str]:
    keys: set[str] = set()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line == f"{section}:":
            for mapping_line in lines[index + 1 :]:
                if mapping_line and not mapping_line.startswith(" "):
                    break
                if mapping_line.startswith("  ") and not mapping_line.startswith(
                    "    "
                ):
                    key = mapping_line.strip().split(":", 1)[0]
                    if key:
                        keys.add(key)
            break
    return frozenset(keys)


def _list_item_names(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:"):
            names.append(stripped.split(":", 1)[1].strip())
    return names


def _probe_paths(text: str, probe: str) -> frozenset[str]:
    paths: set[str] = set()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != f"{probe}:":
            continue
        probe_indent = len(line) - len(line.lstrip())
        for probe_line in lines[index + 1 :]:
            if probe_line.strip() and not probe_line.startswith(
                " " * (probe_indent + 1)
            ):
                break
            stripped = probe_line.strip()
            if stripped.startswith("path:"):
                paths.add(stripped.split(":", 1)[1].strip())
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
