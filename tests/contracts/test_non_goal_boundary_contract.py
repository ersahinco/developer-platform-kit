from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

import yaml

from ._helpers import ROOT


ALLOWED_CATALOG_BRANCHES = {"aws", "local-compose", "local-kubernetes"}
NON_PRODUCT_ROOTS = {"docs", "tests", ".kiro"}
FORBIDDEN_FULL_COMPONENTS = {
    "charts",
    "control-plane",
    "control-planes",
    "cloud-abstraction",
    "cloud-abstractions",
    "provider-abstraction",
    "provider-abstractions",
    "provider-neutral",
}
FORBIDDEN_TOKENS = {
    "generator",
    "generators",
    "helm",
    "portal",
    "portals",
    "scaffold",
    "scaffolder",
}


def _tracked_paths() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return [Path(line) for line in completed.stdout.splitlines()]


def _product_paths() -> list[Path]:
    return [
        path
        for path in _tracked_paths()
        if path.parts and path.parts[0] not in NON_PRODUCT_ROOTS
    ]


def _normalized_component(component: str) -> str:
    return Path(component).stem.lower().replace("_", "-")


def _has_forbidden_path_component(path: Path) -> bool:
    for component in path.parts:
        normalized = _normalized_component(component)
        if normalized in FORBIDDEN_FULL_COMPONENTS:
            return True
        if set(normalized.split("-")) & FORBIDDEN_TOKENS:
            return True
    return False


def _yaml_documents(path: Path) -> list[dict[str, Any]]:
    if path.suffix not in {".yaml", ".yml"}:
        return []
    documents = yaml.safe_load_all((ROOT / path).read_text(encoding="utf-8"))
    return [document for document in documents if isinstance(document, dict)]


def test_repo_does_not_grow_forbidden_expansion_surfaces() -> None:
    forbidden_paths = sorted(
        str(path)
        for path in _product_paths()
        if path.name in {"Chart.yaml", ".helmignore"}
        or _has_forbidden_path_component(path)
    )

    assert forbidden_paths == []


def test_repo_does_not_define_kubernetes_crds() -> None:
    crd_paths = sorted(
        str(path)
        for path in _product_paths()
        if "crds" in {_normalized_component(component) for component in path.parts}
        or any(
            document.get("kind") == "CustomResourceDefinition"
            for document in _yaml_documents(path)
        )
    )

    assert crd_paths == []


def test_infra_catalog_branches_stay_explicit_runtime_targets() -> None:
    branches = {
        path.parts[2]
        for path in _tracked_paths()
        if len(path.parts) > 3 and path.parts[:2] == ("infra", "catalog")
    }

    assert branches == ALLOWED_CATALOG_BRANCHES
