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
        "help-proof": [
            "monorepo-capability-profile",
            "monorepo-capability-profile-md",
            "monorepo-capability-profile-check",
            "workload-admission-check",
            "workload-readiness-check",
            "local-compose-live-proof",
            "local-kubernetes-contracts",
        ],
        "help-cloud": [
            "platform-doctor-cloud",
            "platform-toolkit-validate-cloud",
            "security-readiness",
        ],
        "help-operator": ["release-evidence-runs", "incident-evidence"],
    }
    for target, expected_lines in focused_views.items():
        output = _run_make_help(target)
        for expected_line in expected_lines:
            assert expected_line in output


def test_readme_opens_with_delivery_toolkit_north_star() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    opener = " ".join(readme.splitlines()[2:6])

    assert "This delivery toolkit helps teams define portable workload boundaries" in (
        opener
    )
    assert "prove them locally" in opener
    assert "deliver them through GitHub Actions" in opener
    assert "realize them at the platform edge with runtime evidence" in opener
    assert "without hiding standard DevOps tools behind a framework" in opener


def test_proof_ladder_commands_stay_discoverable() -> None:
    proof_ladder = (ROOT / "docs" / "proof-ladder.md").read_text(encoding="utf-8")
    referenced_targets = {
        match.group(1)
        for match in [
            *MAKE_TARGET_PATTERN.finditer(proof_ladder),
            *INLINE_MAKE_TARGET_PATTERN.finditer(proof_ladder),
        ]
    }
    focused_help = "\n".join(
        _run_make_help(target)
        for target in ["help-local", "help-proof", "help-cloud", "help-operator"]
    )

    assert "## Change-To-Proof Map" in proof_ladder
    assert "Start with the cheapest proof that covers the boundary changed." in (
        proof_ladder
    )
    assert "Workload metadata, owner, ports, config, secrets, class, or use cases" in (
        proof_ladder
    )
    assert "Dapr pub/sub, outbox, CloudEvents" in proof_ladder
    assert "Isolated live Compose evidence is needed" in proof_ladder
    assert "make local-compose-live-proof" in proof_ladder
    assert "GitHub workflow inputs, dry-run commands" in proof_ladder
    assert "Operator docs, release evidence, incident evidence, or runbooks" in (
        proof_ladder
    )
    assert (
        sorted(target for target in referenced_targets if target not in focused_help)
        == []
    )


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
    assert "make local-compose-live-proof" in docs
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


def test_local_kubernetes_doctor_checks_direct_proof_tools() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    doctor_target = re.search(
        r"_local-kubernetes-doctor:.*?(?=^\.PHONY:)",
        makefile,
        re.MULTILINE | re.DOTALL,
    )

    assert doctor_target is not None
    for tool in ["uv", "jq", "docker", "kind", "kubectl"]:
        assert f"command -v {tool}" in doctor_target.group(0)


def test_cloud_validation_includes_safe_infra_readiness_before_dry_runs() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    target = re.search(
        r"platform-toolkit-validate-cloud:.*?(?=^\.PHONY:)",
        makefile,
        re.MULTILINE | re.DOTALL,
    )

    assert target is not None
    body = target.group(0)
    assert "$(MAKE) security-readiness" in body
    assert "$(MAKE) lint-policy" in body
    assert "$(MAKE) infra-validate-local" in body
    assert "$(MAKE) workflow-dry-run-validate" in body
    assert body.index("$(MAKE) workload-readiness-check") < body.index(
        "$(MAKE) security-readiness"
    )
    assert body.index("$(MAKE) security-readiness") < body.index("$(MAKE) lint-policy")
    assert body.index("$(MAKE) lint-policy") < body.index(
        "$(MAKE) infra-validate-local"
    )
    assert body.index("$(MAKE) infra-validate-local") < body.index(
        "$(MAKE) workflow-dry-run-validate"
    )


def test_security_readiness_uses_standard_local_security_tools() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    target = re.search(
        r"security-readiness:.*?(?=^\.PHONY:)",
        makefile,
        re.MULTILINE | re.DOTALL,
    )

    assert target is not None
    body = target.group(0)
    assert "$(MAKE) secret-scan" in body
    assert "$(MAKE) dependency-audit" in body
