"""Exercise OIDC login, three real scaffolder tasks, Git publishing, and CLI parity."""

import io
import json
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bootstrap import PORTAL, context, login, request, secret
from prepare import BASE_URL, STATE, TOOLKIT, TOOLKIT_REF


def main():
    if (STATE / "github-owner").exists():
        raise SystemExit(
            "Smoke creates local Gitea repos only. GitHub publishing requires a deliberate browser task."
        )
    sys.path.insert(0, str(TOOLKIT))
    from scaffold.new_repo import (
        available_templates,
        example_values,
        render,
        resolve_values,
    )

    auth = {"Authorization": "Bearer " + login(), "Content-Type": "application/json"}
    catalog = request(PORTAL + "/api/catalog/entities?filter=kind=template", headers=auth)
    assert {item["metadata"]["name"] for item in catalog} == {
        "platform-app",
        "platform-infra",
        "platform-data",
    }
    git_auth = {"Authorization": "token " + secret("gitea", "gitea-credential")["token"]}
    suffix = uuid.uuid4().hex[:8]
    for template in available_templates():
        name = f"smoke-{template.name}-{suffix}"
        values = example_values(template) | {
            "OWNER": "platform-engineering",
            "REPOSITORY": f"platform/{name}",
            "REPOSITORY_BASE_URL": BASE_URL,
            "TOOLKIT_REPOSITORY": "ersahinco/developer-platform-kit",
            "TOOLKIT_REF": TOOLKIT_REF,
        }
        for key in ("WORKLOAD_NAME", "STACK_NAME", "PIPELINE_NAME"):
            if key in values:
                values[key] = name
        parameters = {
            key: value
            for key, value in values.items()
            if key not in {"REPOSITORY", "REPOSITORY_BASE_URL"}
        }
        parameters["repoUrl"] = "cnoe.localtest.me:8443?" + urlencode(
            {"owner": "platform", "repo": name}
        )
        task = request(
            PORTAL + "/api/scaffolder/v2/tasks",
            headers=auth,
            data=json.dumps(
                {
                    "templateRef": f"template:default/platform-{template.name}",
                    "values": parameters,
                }
            ).encode(),
        )
        task_url = PORTAL + "/api/scaffolder/v2/tasks/" + task["id"]
        print(f"{template.name}: task {task['id']}", flush=True)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            status = request(task_url, headers=auth)["status"]
            if status == "completed":
                break
            if status not in {"open", "processing"}:
                raise RuntimeError(
                    f"{template.name} task {task['id']} ended with {status}; inspect it in Backstage."
                )
            time.sleep(2)
        else:
            raise TimeoutError(f"{template.name} task is still {status}; it has not completed.")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render(template, root, resolve_values(template, values))
            url = BASE_URL + f"/api/v1/repos/platform/{name}/archive/main.zip"
            with urlopen(Request(url, headers=git_auth), context=context(), timeout=30) as response:
                archive = zipfile.ZipFile(io.BytesIO(response.read()))
            actual = {
                file.split("/", 1)[1]: archive.read(file)
                for file in archive.namelist()
                if not file.endswith("/")
            }
            expected = {
                str(file.relative_to(root)): file.read_bytes()
                for file in root.rglob("*")
                if file.is_file()
            }
            assert actual.keys() == expected.keys(), f"{template.name}: published file set differs"
            for file in expected:
                assert actual[file] == expected[file], f"{template.name}/{file}: content differs"
        for attempt in range(30):
            try:
                entity = request(
                    PORTAL + f"/api/catalog/entities/by-name/component/default/{name}",
                    headers=auth,
                )
                break
            except HTTPError as error:
                if error.code != 404:
                    raise
                time.sleep(2)
        else:
            raise TimeoutError(f"{name} was published but has not appeared in the catalog.")
        assert (
            entity["metadata"]["annotations"]["backstage.io/source-location"]
            == f"url:{BASE_URL}/platform/{name}"
        )
        print(
            f"{template.name}: published {len(expected)} identical files and registered {name}",
            flush=True,
        )
    print(
        "All three portal/CLI paths passed. Smoke repositories remain in the local platform organization."
    )


if __name__ == "__main__":
    main()
