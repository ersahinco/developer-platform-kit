from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAKE_TARGET_PATTERN = re.compile(
    r"^\s*(?:[A-Z0-9_]+=(?:\S+)\s+)*make\s+([a-zA-Z0-9_-]+)\b",
    re.MULTILINE,
)
INLINE_MAKE_TARGET_PATTERN = re.compile(
    r"`(?:[A-Z0-9_]+=(?:\S+)\s+)*make\s+([a-zA-Z0-9_-]+)\b[^`]*`"
)
MAKEFILE_TARGET_PATTERN = re.compile(r"^([a-zA-Z0-9_-]+):", re.MULTILINE)


def test_documented_make_targets_exist() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    declared_targets = set(MAKEFILE_TARGET_PATTERN.findall(makefile))
    markdown_paths = [
        ROOT / "README.md",
        *sorted((ROOT / "docs").rglob("*.md")),
    ]

    referenced_targets: dict[str, list[str]] = {}
    for path in markdown_paths:
        text = path.read_text(encoding="utf-8")
        matches = [
            *MAKE_TARGET_PATTERN.finditer(text),
            *INLINE_MAKE_TARGET_PATTERN.finditer(text),
        ]
        for match in matches:
            target = match.group(1)
            referenced_targets.setdefault(target, []).append(
                str(path.relative_to(ROOT))
            )

    missing = {
        target: paths
        for target, paths in referenced_targets.items()
        if target not in declared_targets
    }

    assert missing == {}


def _run_make_help(target: str) -> str:
    completed = subprocess.run(
        ["make", target],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return completed.stdout


def test_make_help_points_to_focused_views() -> None:
    help_output = _run_make_help("help")

    assert "Start here\n" in help_output
    assert "help-local" in help_output
    assert "help-proof" in help_output
    assert "help-cloud" in help_output
    assert "help-operator" in help_output
    assert "Run a focused help target instead of scanning every Make target." in (
        help_output
    )
    assert "platform-toolkit-validate-local" not in help_output

    focused_views = {
        "help-local": [
            "platform-doctor",
            "local-app-up",
            "platform-toolkit-smoke-local",
        ],
        "help-proof": ["workload-readiness-check", "local-kubernetes-contracts"],
        "help-cloud": ["platform-doctor-cloud", "platform-toolkit-validate-cloud"],
        "help-operator": ["release-evidence-runs", "incident-evidence"],
    }
    for target, expected_lines in focused_views.items():
        output = _run_make_help(target)
        for expected_line in expected_lines:
            assert expected_line in output


def test_entrypoint_docs_keep_local_proof_and_cloud_readiness_separate() -> None:
    docs = "\n".join(
        [
            (ROOT / "README.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "first-30-minutes.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "local-development.md").read_text(encoding="utf-8"),
        ]
    )

    assert "make platform-doctor" in docs
    assert "make local-app-up" in docs
    assert "make workload-readiness-local" in docs
    assert "make local-kubernetes-admission-report" in docs
    assert "make platform-doctor-cloud" in docs
    assert "GitHub auth" in docs
    assert "cloud-only tools are warnings" in docs


def test_adding_workloads_keeps_static_local_proof_before_live_drills() -> None:
    docs = (ROOT / "docs" / "adding-workloads.md").read_text(encoding="utf-8")

    assert "make workload-readiness-local" in docs
    assert "make workload-readiness-check" in docs
    assert "make local-kubernetes-admission-report" in docs
    assert "make platform-toolkit-smoke-local" in docs
    assert "starts only the app-host services" in docs


def test_fast_smoke_uses_lightweight_local_app_startup() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    smoke_target = re.search(
        r"platform-toolkit-smoke-local:.*?(?=^\.PHONY:)",
        makefile,
        re.MULTILINE | re.DOTALL,
    )

    assert smoke_target is not None
    assert "$(MAKE) local-app-up" in smoke_target.group(0)
    assert "$(MAKE) local-up" not in smoke_target.group(0)
