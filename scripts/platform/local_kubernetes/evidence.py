from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from scripts.platform.local_kubernetes.admission import admission_rows
from scripts.platform.local_kubernetes.constants import DEFAULT_NAMESPACE
from scripts.platform.local_kubernetes.constants import DEFAULT_OUTPUT_DIR
from scripts.platform.local_kubernetes.runner import CommandRunner
from scripts.platform.local_kubernetes.runner import run_command


def collect_evidence_bundle(
    *,
    namespace: str = DEFAULT_NAMESPACE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    runner: CommandRunner = run_command,
) -> dict[str, Any]:
    commands = {
        "pods": ["kubectl", "-n", namespace, "get", "pods", "-o", "wide"],
        "deployments": ["kubectl", "-n", namespace, "get", "deployments", "-o", "wide"],
        "services": ["kubectl", "-n", namespace, "get", "services", "-o", "wide"],
        "jobs": ["kubectl", "-n", namespace, "get", "jobs", "-o", "wide"],
        "endpoints": ["kubectl", "-n", namespace, "get", "endpoints", "-o", "wide"],
        "events": [
            "kubectl",
            "-n",
            namespace,
            "get",
            "events",
            "--sort-by=.lastTimestamp",
        ],
        "api_rollout": [
            "kubectl",
            "-n",
            namespace,
            "rollout",
            "status",
            "deployment/api",
            "--timeout=30s",
        ],
        "api_describe": ["kubectl", "-n", namespace, "describe", "deployment/api"],
        "api_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "deployment/api",
            "--tail=120",
        ],
        "event_consumer_describe": [
            "kubectl",
            "-n",
            namespace,
            "describe",
            "deployment/event-consumer",
        ],
        "event_consumer_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "deployment/event-consumer",
            "-c",
            "event-consumer",
            "--tail=160",
        ],
        "event_consumer_daprd_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "deployment/event-consumer",
            "-c",
            "daprd",
            "--tail=160",
        ],
        "redis_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "deployment/redis",
            "--tail=120",
        ],
        "backfill_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "job/backfill-worker",
            "--tail=120",
        ],
        "data_export_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "job/data-export-job",
            "--tail=120",
        ],
        "integration_check_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "job/integration-check-job",
            "--tail=120",
        ],
        "operational_snapshot_logs": [
            "kubectl",
            "-n",
            namespace,
            "logs",
            "job/operational-snapshot-job",
            "--tail=120",
        ],
    }
    results = {name: asdict(runner(command)) for name, command in commands.items()}
    status = (
        "succeeded"
        if all(result["returncode"] == 0 for result in results.values())
        else "failed"
    )
    evidence = {
        "runtime_target": "local-kubernetes",
        "namespace": namespace,
        "status": status,
        "commands": results,
        "admission": [asdict(row) for row in admission_rows()],
    }
    return write_evidence(evidence, output_dir, "local-kubernetes-evidence")


def write_evidence(
    evidence: dict[str, Any],
    output_dir: Path,
    stem: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    evidence = {
        **evidence,
        "evidence_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    json_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(markdown(evidence), encoding="utf-8")
    return evidence


def markdown(evidence: dict[str, Any]) -> str:
    lines = [
        "# Local Kubernetes Evidence",
        "",
        f"- runtime_target: `{evidence['runtime_target']}`",
        f"- namespace: `{evidence['namespace']}`",
        f"- status: `{evidence['status']}`",
    ]
    if "candidate_image" in evidence:
        lines.extend(
            [
                f"- initial_image: `{evidence['initial_image']}`",
                f"- candidate_image: `{evidence['candidate_image']}`",
            ]
        )
    lines.append("")
    if "steps" in evidence:
        lines.append("## Rollout Steps")
        for step in evidence["steps"]:
            lines.append(f"- `{step['name']}`: exit `{step['returncode']}`")
    if "commands" in evidence:
        lines.append("## Captured Commands")
        for name, result in evidence["commands"].items():
            lines.append(f"- `{name}`: exit `{result['returncode']}`")
    if "admission" in evidence:
        lines.append("## Admission")
        for row in evidence["admission"]:
            blockers = "; ".join(row["blockers"]) if row["blockers"] else "none"
            lines.append(
                f"- `{row['workload']}`: `{row['status']}`; blockers: {blockers}"
            )
    lines.append("")
    return "\n".join(lines)
