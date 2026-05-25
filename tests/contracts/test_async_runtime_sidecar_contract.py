from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_async_runtime_config_loader_overrides_aws_cli_entrypoint() -> None:
    text = (ROOT / "infra/app/workload_jobs.tf").read_text(encoding="utf-8")

    assert "image     = var.runtime_config_loader_image" in text
    assert 'entryPoint = ["/bin/sh", "-c"]' in text
    assert "command = [local.async_eventing_dapr_config_loader_command]" in text
