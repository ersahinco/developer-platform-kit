from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_async_runtime_config_loader_overrides_aws_cli_entrypoint() -> None:
    text = (ROOT / "infra/app/workload_jobs.tf").read_text(encoding="utf-8")

    loader_block = re.search(
        r'name\s*=\s*"dapr-config-loader".*?image\s*=\s*var\.runtime_config_loader_image.*?command\s*=\s*\[local\.async_eventing_dapr_config_loader_command\]',
        text,
        re.DOTALL,
    )

    assert loader_block is not None
    block_text = loader_block.group(0)
    assert re.search(r'entryPoint\s*=\s*\["/bin/sh",\s*"-c"\]', block_text)
    assert re.search(r'name\s*=\s*"AWS_REGION"', block_text)
    assert re.search(r'name\s*=\s*"AWS_DEFAULT_REGION"', block_text)
