"""Keep client configuration inputs aligned with the native Backstage config."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_hosting_supplies_every_required_configuration_value() -> None:
    required = set(
        re.findall(r"\$\{([A-Z_]+)\}", (ROOT / "platform/backstage/entra.yaml").read_text())
    )
    example = (ROOT / "platform/hosting/portal.env.example").read_text()
    assert required <= set(re.findall(r"^([A-Z_]+)=", example, re.MULTILINE))

    # BaseLoader preserves the shape while treating CloudFormation tags as data.
    stack = yaml.load((ROOT / "platform/hosting/aws.yaml").read_text(), Loader=yaml.BaseLoader)
    container = stack["Resources"]["Task"]["Properties"]["ContainerDefinitions"][0]
    injected = {item["Name"] for item in container["Secrets"] if isinstance(item, dict)}
    assert required <= injected
    assert all(
        item["ValueFrom"] == "${ConfigurationSecret}:" + item["Name"] + "::"
        for item in container["Secrets"]
        if isinstance(item, dict)
    )
