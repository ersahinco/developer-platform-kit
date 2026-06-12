from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Callable

from scripts.platform.local_kubernetes_proof import API_METRIC_NEEDLE
from scripts.platform.local_kubernetes_proof import CommandResult
from scripts.platform.local_kubernetes_proof import admission_rows
from scripts.platform.local_kubernetes_proof import collect_evidence_bundle
from scripts.platform.local_kubernetes_proof import dapr_eventing_proof
from scripts.platform.local_kubernetes_proof import rollout_rollback_proof


ROOT = Path(__file__).resolve().parents[2]


def test_admission_report_marks_current_local_kubernetes_workloads_ready() -> None:
    rows = {row.workload: row for row in admission_rows()}

    assert rows["api"].status == "ready"
    assert rows["event_consumer"].status == "ready"
    assert rows["backfill_worker"].status == "ready"
    assert rows["data_export_job"].status == "ready"
    assert rows["operational_snapshot_job"].status == "ready"
    assert rows["integration_check_job"].status == "ready"
    assert rows["event_consumer"].blockers == []
    assert "Dapr pub/sub sidecar and Redis proof path" in rows["event_consumer"].checks


def test_admission_report_cli_outputs_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/platform/local_kubernetes_proof.py",
            "admission-report",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    rows = json.loads(completed.stdout)
    assert any(row["workload"] == "api" and row["status"] == "ready" for row in rows)


def test_evidence_bundle_captures_kubernetes_state(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def runner(command: list[str]) -> CommandResult:
        commands.append(command)
        return CommandResult(command=command, returncode=0, stdout="ok", stderr="")

    evidence = collect_evidence_bundle(output_dir=tmp_path, runner=runner)

    assert evidence["status"] == "succeeded"
    assert (tmp_path / "local-kubernetes-evidence.json").exists()
    assert (tmp_path / "local-kubernetes-evidence.md").exists()
    assert ["kubectl", "-n", "aws-sdlc-local", "get", "pods", "-o", "wide"] in (
        commands
    )
    assert any(
        command[:5] == ["kubectl", "-n", "aws-sdlc-local", "logs", "deployment/api"]
        for command in commands
    )


def test_rollout_rollback_proof_updates_then_restores_image(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def runner(command: list[str]) -> CommandResult:
        commands.append(command)
        stdout = "ok"
        joined = " ".join(command)
        if ".spec.template.spec.containers" in joined:
            stdout = "aws-sdlc-containers-api:local-kubernetes"
        if ".subsets[*].addresses[*].ip" in joined:
            stdout = "10.244.0.12"
        if command and command[-1] == "http://api:8000/metrics":
            stdout = API_METRIC_NEEDLE
        return CommandResult(command=command, returncode=0, stdout=stdout, stderr="")

    evidence = rollout_rollback_proof(
        candidate_image="aws-sdlc-containers-api:local-kubernetes-rollout",
        output_dir=tmp_path,
        runner=runner,
    )

    assert evidence["status"] == "succeeded"
    assert evidence["initial_image"] == "aws-sdlc-containers-api:local-kubernetes"
    assert evidence["candidate_image"] == (
        "aws-sdlc-containers-api:local-kubernetes-rollout"
    )
    assert any(
        command[:5] == ["kubectl", "-n", "aws-sdlc-local", "set", "image"]
        for command in commands
    )
    assert any(
        command[:6]
        == ["kubectl", "-n", "aws-sdlc-local", "rollout", "undo", "deployment/api"]
        for command in commands
    )
    assert any(
        command[:6]
        == ["kubectl", "-n", "aws-sdlc-local", "wait", "--for=condition=ready", "pod"]
        for command in commands
    )
    assert any(
        command[:6] == ["kubectl", "-n", "aws-sdlc-local", "get", "endpoints", "api"]
        for command in commands
    )
    assert any("--retry-connrefused" in command for command in commands)
    assert (tmp_path / "local-kubernetes-rollout-proof.json").exists()


def test_dapr_eventing_proof_creates_order_and_waits_for_consumer_log(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []
    log_attempts = 0

    def runner(command: list[str]) -> CommandResult:
        nonlocal log_attempts
        commands.append(command)
        joined = " ".join(command)
        stdout = "ok"
        if ".subsets[*].addresses[*].ip" in joined:
            stdout = "10.244.0.44"
        if command and command[-1] == "http://event-consumer:8081/metrics":
            stdout = 'workload_info{workload="event_consumer",workload_class="internal-service"} 1.0'
        if "api-order-eventing-proof" in command:
            stdout = '{"id": 42, "status": "SUBMITTED"}'
        if command[:4] == ["kubectl", "-n", "aws-sdlc-local", "logs"]:
            log_attempts += 1
            stdout = (
                '{"event": "event_consumed", "event_id": "order.created.v1:42"}'
                if log_attempts > 1
                else "starting"
            )
        return CommandResult(command=command, returncode=0, stdout=stdout, stderr="")

    evidence = dapr_eventing_proof(
        output_dir=tmp_path,
        runner=runner,
        monotonic=_fake_monotonic(),
        sleep=lambda _: None,
    )

    assert evidence["status"] == "succeeded"
    assert evidence["order_id"] == 42
    assert any("seed-eventing-customer" in command for command in commands)
    assert any("api-order-eventing-proof" in command for command in commands)
    assert any(
        command[:6] == ["kubectl", "-n", "aws-sdlc-local", "get", "endpoints", "redis"]
        for command in commands
    )
    assert any(step["name"] == "event_consumed_logs" for step in evidence["steps"])
    assert (tmp_path / "local-kubernetes-dapr-eventing-proof.json").exists()


def _fake_monotonic() -> Callable[[], float]:
    current = 0.0

    def monotonic() -> float:
        nonlocal current
        current += 1.0
        return current

    return monotonic
