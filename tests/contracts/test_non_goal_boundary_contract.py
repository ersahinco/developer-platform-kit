from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

import yaml

from ._helpers import ROOT
from ._helpers import load_json


CATALOG_BRANCH_NAMES = {"aws-ecs": "aws"}
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
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return [
        Path(line) for line in completed.stdout.splitlines() if (ROOT / line).exists()
    ]


def _product_paths() -> list[Path]:
    return [
        path
        for path in _tracked_paths()
        if path.parts and path.parts[0] not in NON_PRODUCT_ROOTS
    ]


def _catalog_branches_for_active_runtime_targets() -> set[str]:
    runtime_defaults = load_json("platform/runtime-defaults.json")
    runtime_targets = runtime_defaults["runtime_targets"]
    assert isinstance(runtime_targets, dict)
    branches: set[str] = set()
    for runtime_target in runtime_targets:
        target = str(runtime_target)
        branches.add(CATALOG_BRANCH_NAMES.get(target, target))
    return branches


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

    assert branches == _catalog_branches_for_active_runtime_targets()
