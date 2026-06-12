from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from scripts.platform.local_kubernetes.admission import AdmissionRow
from scripts.platform.local_kubernetes.admission import admission_rows
from scripts.platform.local_kubernetes.constants import DEFAULT_NAMESPACE
from scripts.platform.local_kubernetes.constants import DEFAULT_OUTPUT_DIR
from scripts.platform.local_kubernetes.dapr import dapr_eventing_proof
from scripts.platform.local_kubernetes.evidence import collect_evidence_bundle
from scripts.platform.local_kubernetes.rollout import rollout_rollback_proof


def _print_admission(rows: list[AdmissionRow], *, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps([asdict(row) for row in rows], indent=2, sort_keys=True))
        return
    print("\t".join(["workload", "kind", "status", "manifest", "blockers"]))
    for row in rows:
        blockers = "; ".join(row.blockers) if row.blockers else "-"
        print(
            "\t".join(
                [row.workload, row.kind, row.status, row.manifest or "-", blockers]
            )
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local Kubernetes rollout, evidence, and admission proof helpers."
    )
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    subparsers = parser.add_subparsers(dest="command", required=True)

    rollout = subparsers.add_parser("rollout-proof")
    rollout.add_argument("--deployment", default="api")
    rollout.add_argument("--container", default="api")
    rollout.add_argument("--candidate-image", required=True)

    subparsers.add_parser("dapr-eventing-proof")

    subparsers.add_parser("evidence-bundle")

    admission = subparsers.add_parser("admission-report")
    admission.add_argument("--format", choices=["table", "json"], default="table")

    args = parser.parse_args(argv)

    if args.command == "rollout-proof":
        evidence = rollout_rollback_proof(
            namespace=args.namespace,
            deployment=args.deployment,
            container=args.container,
            candidate_image=args.candidate_image,
            output_dir=args.output_dir,
        )
        print(f"wrote {evidence['evidence_path']}")
        print(f"wrote {evidence['markdown_path']}")
        return 0
    if args.command == "evidence-bundle":
        evidence = collect_evidence_bundle(
            namespace=args.namespace, output_dir=args.output_dir
        )
        print(f"wrote {evidence['evidence_path']}")
        print(f"wrote {evidence['markdown_path']}")
        return 0 if evidence["status"] == "succeeded" else 1
    if args.command == "dapr-eventing-proof":
        evidence = dapr_eventing_proof(
            namespace=args.namespace,
            output_dir=args.output_dir,
        )
        print(f"wrote {evidence['evidence_path']}")
        print(f"wrote {evidence['markdown_path']}")
        return 0
    if args.command == "admission-report":
        _print_admission(admission_rows(), output_format=args.format)
        return 0
    raise AssertionError(args.command)
