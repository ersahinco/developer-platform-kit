from __future__ import annotations

import json
from pathlib import Path

from ._helpers import ROOT


PROVIDER_TOKENS = {
    "aws",
    "cloudflare",
    "ecs",
    "hetzner",
    "hcloud",
    "rds",
    "route53",
    "s3",
    "supabase",
}


def _source_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".py", ".json", ".yaml", ".yml"}
    ]


def test_domain_and_application_packages_do_not_name_providers() -> None:
    offenders: list[str] = []
    for relative_root in ["packages/domain", "packages/application"]:
        for path in _source_files(ROOT / relative_root):
            lowered = path.read_text(encoding="utf-8").lower()
            for token in PROVIDER_TOKENS:
                if token in lowered:
                    offenders.append(f"{path.relative_to(ROOT)}:{token}")

    assert offenders == []


def test_workload_metadata_contains_capabilities_not_provider_bindings() -> None:
    document = json.loads(
        (ROOT / "platform/workloads.json").read_text(encoding="utf-8")
    )
    for workload in document["workloads"]:
        assert "runtime" not in workload
        assert all(
            not any(token in name.lower() for token in PROVIDER_TOKENS)
            for name in workload["config"]["env"] + workload["config"]["secrets"]
        )

    # Package coordinates retain the repository's historical project name;
    # runtime bindings and provider-specific config belong outside this file.
    portable_document = json.loads(json.dumps(document))
    for workload in portable_document["workloads"]:
        workload["image"].pop("package", None)
    serialized = json.dumps(portable_document, sort_keys=True).lower()

    assert all(token not in serialized for token in PROVIDER_TOKENS)
