"""Exercise smoke's real task inputs and catalog lookup against an offline publisher."""

import io
import json
import runpy
import zipfile
from pathlib import Path
from urllib.parse import parse_qs

import pytest
import yaml

from scaffold.backstage import export
from scaffold.new_repo import available_templates, example_values, render, resolve_values


@pytest.mark.parametrize("fixed_names", [False, True])
def test_smoke_handles_editable_and_fixed_workload_names(monkeypatch, tmp_path, fixed_names):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "platform"))
    monkeypatch.setenv("KUBECONFIG", str(tmp_path / "unused-kubeconfig"))
    main = runpy.run_path("platform/smoke.py")["main"]
    scope = main.__globals__
    base_url = scope["BASE_URL"]
    fixed = {"OWNER": "payments"}
    if fixed_names:
        fixed |= {"WORKLOAD_NAME": "api", "STACK_NAME": "infra", "PIPELINE_NAME": "daily"}
    export(tmp_path / "templates", "gitea", base_url, ("platform",), fixed)
    templates = {t.name: t for t in available_templates()}
    catalog = [
        json.loads(path.read_text()) for path in (tmp_path / "templates").glob("*/template.yaml")
    ]
    registered, looked_up = {}, []
    archive = io.BytesIO()

    def request(url, *, headers=None, data=None):
        if url.endswith("entities?filter=kind=template"):
            return catalog
        if data is not None:
            task = json.loads(data)
            template = templates[task["templateRef"].removeprefix("template:default/platform-")]
            entity = next(e for e in catalog if e["spec"]["type"] == template.name)
            form = task["values"].copy()
            assert form.keys() <= entity["spec"]["parameters"][0]["properties"].keys()
            repo = parse_qs(form.pop("repoUrl").split("?", 1)[1])["repo"][0]
            values = example_values(template) | entity["spec"]["steps"][0]["input"]["values"] | form
            values |= {"REPOSITORY": f"platform/{repo}", "REPOSITORY_BASE_URL": base_url}
            output = tmp_path / repo
            render(template, output, resolve_values(template, values))
            component = yaml.safe_load((output / "catalog-info.yaml").read_text())
            registered[component["metadata"]["name"]] = component
            archive.seek(0)
            archive.truncate()
            with zipfile.ZipFile(archive, "w") as zipped:
                for path in output.rglob("*"):
                    if path.is_file():
                        zipped.write(path, f"{repo}/{path.relative_to(output)}")
            return {"id": repo}
        if "/tasks/" in url:
            return {"status": "completed"}
        name = url.rsplit("/", 1)[1]
        looked_up.append(name)
        return registered[name]

    for key, value in {
        "STATE": tmp_path,
        "request": request,
        "login": lambda: "offline-token",
        "secret": lambda *args: {"token": "offline-token"},
        "context": lambda: None,
        "urlopen": lambda *args, **kwargs: io.BytesIO(archive.getvalue()),
    }.items():
        monkeypatch.setitem(scope, key, value)
    main()
    assert set(looked_up) == set(registered)
    assert len(looked_up) == 3
