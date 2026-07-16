from __future__ import annotations

from pathlib import Path
import re

import yaml


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


def test_aws_runtime_uses_the_production_dapr_profile() -> None:
    text = (ROOT / "infra/app/messaging.tf").read_text(encoding="utf-8")

    production_profile = "../../platform/concerns/dapr/profiles/production"
    assert f"{production_profile}/components/async-events-pubsub.yaml" in text
    assert f"{production_profile}/components/resiliency.yaml" in text
    assert not list((ROOT / "infra/app/templates/dapr").glob("*"))


def test_pubsub_components_are_scoped_to_the_event_consumer() -> None:
    for profile in ["local", "production"]:
        component = (
            ROOT
            / "platform"
            / "concerns"
            / "dapr"
            / "profiles"
            / profile
            / "components"
            / "async-events-pubsub.yaml"
        ).read_text(encoding="utf-8")

        assert "scopes:\n  - event-consumer" in component


def test_booking_dapr_sidecar_stays_internal_to_the_compose_network() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))

    assert "ports" not in compose["services"]["booking-api-dapr"]
