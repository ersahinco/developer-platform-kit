from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised by host-python Make usage
    yaml = None  # type: ignore[assignment]

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


def _load_json(path: str) -> dict[str, Any]:
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _documents() -> list[dict[str, Any]]:
    if yaml is None:
        return _documents_without_yaml()

    documents: list[dict[str, Any]] = []
    for path in sorted(LOCAL_KUBERNETES_ROOT.glob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if isinstance(document, dict):
                documents.append(document)
    return documents


def _documents_without_yaml() -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for path in sorted(LOCAL_KUBERNETES_ROOT.glob("*.yaml")):
        for text in re.split(
            r"^---\s*$", path.read_text(encoding="utf-8"), flags=re.MULTILINE
        ):
            document = _document_from_text(text)
            if document:
                documents.append(document)
    return documents


def _document_from_text(text: str) -> dict[str, Any] | None:
    kind = _match(text, r"^kind:\s*(\S+)\s*$")
    name = _match(
        text,
        r"^metadata:\s*\n(?:^[ \t].*\n)*?^[ \t]{2}name:\s*([^\s#]+)\s*$",
    )
    if kind is None or name is None:
        return None

    document: dict[str, Any] = {"kind": kind, "metadata": {"name": name}}
    if kind == "ConfigMap":
        document["data"] = _mapping_keys(text, "data")
    if kind == "Secret":
        document["stringData"] = _mapping_keys(text, "stringData")

    workload = _match(text, r"^[ \t]+workload:\s*([^\s#]+)\s*$")
    restart_policy = _match(text, r"^[ \t]+restartPolicy:\s*([^\s#]+)\s*$")
    containers = [
        {"name": value}
        for value in re.findall(
            r"^[ \t]+- name:\s*([^\s#]+)\s*$", text, flags=re.MULTILINE
        )
    ]
    if "/ready" in text or "/health" in text:
        first_container = containers[0] if containers else {}
        if "/ready" in text:
            first_container["readinessProbe"] = {"httpGet": {"path": "/ready"}}
        if "/health" in text:
            first_container["livenessProbe"] = {"httpGet": {"path": "/health"}}
        if containers:
            containers[0] = first_container
        else:
            containers = [first_container]

    if workload or restart_policy or containers:
        template: dict[str, Any] = {"metadata": {"labels": {}}, "spec": {}}
        if workload:
            template["metadata"]["labels"]["workload"] = workload
        if restart_policy:
            template["spec"]["restartPolicy"] = restart_policy
        if containers:
            template["spec"]["containers"] = containers
        document["spec"] = {"template": template}

    backoff_limit = _match(text, r"^  backoffLimit:\s*(\d+)\s*$")
    if backoff_limit is not None:
        document.setdefault("spec", {})["backoffLimit"] = int(backoff_limit)
    return document


def _match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1) if match else None


def _mapping_keys(text: str, section: str) -> dict[str, str]:
    match = re.search(
        rf"^{section}:\s*\n(?P<body>(?:^[ \t]{{2}}[^\n]+\n?)*)",
        text,
        flags=re.MULTILINE,
    )
    if not match:
        return {}
    keys = {}
    for line in match.group("body").splitlines():
        key = line.strip().split(":", 1)[0]
        if key:
            keys[key] = ""
    return keys


def _metadata(document: dict[str, Any]) -> dict[str, Any]:
    metadata = document.get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _workload_label(document: dict[str, Any]) -> str | None:
    template = document.get("spec", {}).get("template", {})
    metadata = template.get("metadata", {}) if isinstance(template, dict) else {}
    labels = metadata.get("labels", {}) if isinstance(metadata, dict) else {}
    workload = labels.get("workload") if isinstance(labels, dict) else None
    return workload if isinstance(workload, str) else None


def _document_name(document: dict[str, Any]) -> str:
    name = _metadata(document).get("name", "")
    return str(name)


def _document_by_kind_name() -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(document.get("kind")), _document_name(document)): document
        for document in _documents()
    }


def _workload_manifest(workload: dict[str, Any]) -> dict[str, Any] | None:
    expected_kind = "Deployment" if workload["kind"] == "service" else "Job"
    for document in _documents():
        if (
            document.get("kind") == expected_kind
            and _workload_label(document) == workload["name"]
        ):
            return document
    return None


def _config_names(workload: dict[str, Any]) -> set[str]:
    config = workload["config"]
    return set(config["env"]) | set(config["secrets"])


def admission_rows() -> list[AdmissionRow]:
    workloads = _load_json("platform/workloads.json")["workloads"]
    documents = _document_by_kind_name()
    config_map = documents.get(("ConfigMap", "workload-config"), {})
    secret = documents.get(("Secret", "workload-secrets"), {})
    config_names = set(config_map.get("data", {}))
    secret_names = set(secret.get("stringData", {}))
    available_config = config_names | secret_names
    rows: list[AdmissionRow] = []

    for workload in workloads:
        supported = "local-kubernetes" in workload["runtime"]["supported"]
        manifest = _workload_manifest(workload)
        checks: list[str] = []
        blockers: list[str] = []

        if not supported:
            blockers.append("runtime.supported does not include local-kubernetes")
        if manifest is None:
            blockers.append("no local Kubernetes Deployment/Job manifest")
            manifest_name = ""
        else:
            manifest_name = f"{manifest['kind']}/{_document_name(manifest)}"
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
                service = documents.get(("Service", _document_name(manifest or {})))
                container = _first_container(manifest)
                if service is None:
                    blockers.append("no matching local Kubernetes Service")
                elif supported:
                    checks.append(f"Service/{_document_name(service)}")
                if not _has_http_probe(container, "readinessProbe", "/ready"):
                    blockers.append("service lacks /ready readinessProbe")
                if not _has_http_probe(container, "livenessProbe", "/health"):
                    blockers.append("service lacks /health livenessProbe")
                if container and supported:
                    checks.append("health and readiness probes")
            else:
                spec = manifest.get("spec", {}) if isinstance(manifest, dict) else {}
                template_spec = spec.get("template", {}).get("spec", {})
                if template_spec.get("restartPolicy") != "Never":
                    blockers.append("job restartPolicy must be Never")
                if "backoffLimit" not in spec:
                    blockers.append("job backoffLimit is not explicit")
                if supported and template_spec.get("restartPolicy") == "Never":
                    checks.append("bounded job execution")

        if workload.get("dapr"):
            if not _has_local_dapr_eventing(documents, manifest):
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


def _first_container(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(document, dict):
        return None
    containers = (
        document.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    if isinstance(containers, list) and containers:
        container = containers[0]
        return container if isinstance(container, dict) else None
    return None


def _has_http_probe(container: dict[str, Any] | None, probe: str, path: str) -> bool:
    if not isinstance(container, dict):
        return False
    http_get = container.get(probe, {}).get("httpGet", {})
    return isinstance(http_get, dict) and http_get.get("path") == path


def _has_local_dapr_eventing(
    documents: dict[tuple[str, str], dict[str, Any]],
    manifest: dict[str, Any] | None,
) -> bool:
    if not isinstance(manifest, dict):
        return False
    containers = (
        manifest.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    container_names = {
        container.get("name") for container in containers if isinstance(container, dict)
    }
    return (
        "event-consumer" in container_names
        and "daprd" in container_names
        and ("ConfigMap", "dapr-components") in documents
        and ("ConfigMap", "dapr-config") in documents
        and ("Deployment", "redis") in documents
        and ("Service", "redis") in documents
    )
