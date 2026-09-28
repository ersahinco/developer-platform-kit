"""Local lab defaults use the same validation and export as the CLI."""

import json
import runpy
from pathlib import Path

import pytest

from scaffold.backstage import export
from scaffold.new_repo import TemplateError

PLATFORM = Path(__file__).resolve().parents[1] / "platform"


def test_local_defaults_can_target_a_fork(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(PLATFORM))
    monkeypatch.setenv(
        "PORTAL_SET",
        "OWNER=payments AWS_REGION=eu-west-1 TOOLKIT_REPOSITORY=acme/toolkit "
        f"TOOLKIT_REF={'a' * 40} STATE_BUCKET=acme-state",
    )
    values = runpy.run_path(str(PLATFORM / "prepare.py"))["template_values"]()
    export(tmp_path / "templates", fixed_values=values)
    for name in ("app", "infra", "data"):
        template = json.loads((tmp_path / "templates" / name / "template.yaml").read_text())
        assert template["spec"]["owner"] == "payments"
        inputs = template["spec"]["steps"][0]["input"]["values"]
        for key in ("OWNER", "AWS_REGION", "TOOLKIT_REPOSITORY", "TOOLKIT_REF"):
            assert inputs[key] == values[key]
            assert key not in template["spec"]["parameters"][0]["properties"]


def test_local_overrides_still_reject_floating_refs(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(PLATFORM))
    monkeypatch.setenv("PORTAL_SET", "TOOLKIT_REF=main")
    values = runpy.run_path(str(PLATFORM / "prepare.py"))["template_values"]()
    with pytest.raises(TemplateError, match="TOOLKIT_REF"):
        export(tmp_path / "templates", fixed_values=values)
    assert not (tmp_path / "templates").exists()
