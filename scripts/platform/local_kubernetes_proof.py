#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

from pathlib import Path
import sys


_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from scripts.platform.local_kubernetes.admission import AdmissionRow
from scripts.platform.local_kubernetes.admission import admission_rows
from scripts.platform.local_kubernetes.cli import main
from scripts.platform.local_kubernetes.constants import API_METRIC_NEEDLE
from scripts.platform.local_kubernetes.constants import DEFAULT_NAMESPACE
from scripts.platform.local_kubernetes.constants import DEFAULT_OUTPUT_DIR
from scripts.platform.local_kubernetes.constants import EVENT_CONSUMED_NEEDLE
from scripts.platform.local_kubernetes.constants import EVENT_CONSUMER_METRIC_NEEDLE
from scripts.platform.local_kubernetes.constants import LOCAL_KUBERNETES_ROOT
from scripts.platform.local_kubernetes.constants import ROOT
from scripts.platform.local_kubernetes.dapr import dapr_eventing_proof
from scripts.platform.local_kubernetes.evidence import collect_evidence_bundle
from scripts.platform.local_kubernetes.evidence import markdown as _markdown
from scripts.platform.local_kubernetes.evidence import write_evidence as _write_evidence
from scripts.platform.local_kubernetes.rollout import rollout_rollback_proof
from scripts.platform.local_kubernetes.runner import CommandResult
from scripts.platform.local_kubernetes.runner import CommandRunner
from scripts.platform.local_kubernetes.runner import ProofError
from scripts.platform.local_kubernetes.runner import checked
from scripts.platform.local_kubernetes.runner import run_command


__all__ = [
    "API_METRIC_NEEDLE",
    "AdmissionRow",
    "CommandResult",
    "CommandRunner",
    "DEFAULT_NAMESPACE",
    "DEFAULT_OUTPUT_DIR",
    "EVENT_CONSUMED_NEEDLE",
    "EVENT_CONSUMER_METRIC_NEEDLE",
    "LOCAL_KUBERNETES_ROOT",
    "ProofError",
    "ROOT",
    "_markdown",
    "_write_evidence",
    "admission_rows",
    "checked",
    "collect_evidence_bundle",
    "dapr_eventing_proof",
    "main",
    "rollout_rollback_proof",
    "run_command",
]


if __name__ == "__main__":
    raise SystemExit(main())
