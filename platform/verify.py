"""Check live local identity, TLS rejection, destination policy, and cluster privileges."""

import json
import subprocess
from urllib.error import HTTPError

from bootstrap import PORTAL, login, request
from identity import admin


def headers(token):
    return {"Authorization": "Bearer " + token, "Content-Type": "application/json"}


def identity(token):
    return request(PORTAL + "/api/auth/v1/userinfo", headers=headers(token))["claims"]


def denied(token, path, data=None):
    try:
        request(
            PORTAL + path,
            headers=headers(token),
            data=json.dumps(data).encode() if data is not None else None,
        )
    except HTTPError as error:
        assert error.code == 403, f"Expected authorization denial for {path}, got {error.code}."
    else:
        raise AssertionError(f"Unauthorized request accepted: {path}")


def creation_decision(token):
    result = request(
        PORTAL + "/api/permission/authorize",
        headers=headers(token),
        data=json.dumps(
            {
                "items": [
                    {
                        "id": "create-check",
                        "permission": {
                            "type": "basic",
                            "name": "scaffolder.task.create",
                            "attributes": {"action": "create"},
                        },
                    }
                ]
            }
        ).encode(),
    )
    return result["items"][0]["result"]


def verify_groups(creator, api):
    viewer = login("user2")
    for token, name in ((creator, "scaffold-creators"), (viewer, "scaffold-viewers")):
        assert "group:default/" + name in identity(token)["ent"]
        for template in ("app", "infra", "data"):
            entity = request(
                PORTAL + f"/api/catalog/entities/by-name/template/default/platform-{template}",
                headers=headers(token),
            )
            assert entity["kind"] == "Template"
    assert creation_decision(creator) == "ALLOW"
    assert creation_decision(viewer) == "DENY"
    # Valid template inputs: rejection must come from authorization, not validation.
    props = entity["spec"]["parameters"][0]["properties"]
    values = {key: prop.get("default", "example") for key, prop in props.items()}
    values["PIPELINE_NAME"] = "viewer-must-not-create"
    options = props["repoUrl"]["ui:options"]
    values["repoUrl"] = (
        f"{options['allowedHosts'][0]}?owner={options['allowedOwners'][0]}&repo=viewer-must-not-create"
    )
    denied(
        viewer,
        "/api/scaffolder/v2/tasks",
        {
            "templateRef": "template:default/platform-data",
            "values": values,
            "groups": ["scaffold-creators"],
        },
    )
    listed = request(PORTAL + "/api/scaffolder/v2/tasks", headers=headers(viewer))
    assert listed["tasks"] == [] and int(listed["totalTasks"]) == 0, (
        "Viewers must not see task history, including through the list endpoint."
    )
    creator_tasks = request(PORTAL + "/api/scaffolder/v2/tasks", headers=headers(creator))["tasks"]
    if creator_tasks:
        task_path = "/api/scaffolder/v2/tasks/" + creator_tasks[0]["id"]
        denied(viewer, task_path)
        denied(viewer, task_path + "/cancel", {})
    else:
        print("No existing tasks: detail/cancel checks skipped; run portal-smoke in Gitea first.")
    denied(
        viewer,
        "/api/scaffolder/v2/dry-run",
        {"template": entity, "values": values, "directoryContents": []},
    )
    denied(
        viewer,
        "/api/catalog/locations",
        {"type": "url", "target": PORTAL + "/unused.yaml"},
    )
    # Fresh sign-in must reflect membership removal. Always restore the demo account.
    user = api("users?username=user1&exact=true")[0]["id"]
    group = next(g["id"] for g in api("groups") if g["name"] == "scaffold-creators")
    path = f"users/{user}/groups/{group}"
    api(path, method="DELETE")
    try:
        revoked = login("user1")
        assert creation_decision(revoked) == "DENY"
        denied(
            revoked,
            "/api/scaffolder/v2/tasks",
            {"templateRef": "template:default/platform-data", "values": values},
        )
    finally:
        api(path, method="PUT")
    assert creation_decision(login("user1")) == "ALLOW"
    print(
        "Both groups browse all three templates; only creators can scaffold. Viewer API writes and dry-run denied; membership removal and restoration verified."
    )


def main():
    token = login()
    api = admin()
    user = api("users?username=user1&exact=true")[0]
    assert identity(token)["sub"] == "user:default/" + user["id"], "Login must use a stable ID."
    executions = api("authentication/flows/platform-existing-user/executions")
    disabled = {e.get("providerId") for e in executions if e["requirement"] == "DISABLED"}
    assert {
        "idp-create-user-if-unique",
        "idp-confirm-link",
        "idp-email-verification",
    } <= disabled
    auth = headers(token)
    template = request(
        PORTAL + "/api/catalog/entities/by-name/template/default/platform-app",
        headers=auth,
    )
    props = template["spec"]["parameters"][0]["properties"]
    parameters = {name: value.get("default", "example") for name, value in props.items()}
    parameters["WORKLOAD_NAME"] = "rejected-destination"
    host = props["repoUrl"]["ui:options"]["allowedHosts"][0]
    for destination in (
        "unapproved.example?owner=platform&repo=should-not-exist",
        f"{host}?owner=unapproved-destination&repo=should-not-exist",
    ):
        parameters["repoUrl"] = destination
        # Reject at task creation, before any external operation can run.
        try:
            request(
                PORTAL + "/api/scaffolder/v2/tasks",
                headers=auth,
                data=json.dumps(
                    {
                        "templateRef": "template:default/platform-app",
                        "values": parameters,
                    }
                ).encode(),
            )
        except HTTPError as error:
            assert error.code == 400, f"Expected rejected task parameters, got {error.code}."
            assert "pattern" in error.read().decode(), (
                "Expected the repository pattern to reject the task."
            )
        else:
            raise AssertionError("Unapproved destination was accepted.")
    command = [
        "kubectl",
        "exec",
        "-n",
        "backstage",
        "deployment/backstage",
        "--",
        "node",
        "-e",
        r"""
const https = require('https');
const url = 'https://cnoe.localtest.me:8443/keycloak/realms/cnoe/.well-known/openid-configuration';
if (process.env.NODE_TLS_REJECT_UNAUTHORIZED === '0') process.exit(1);
https.get(url, res => {
  if (res.statusCode !== 200) process.exit(2);
  res.resume();
  https.get(url, {ca: require('tls').rootCertificates, agent: false}, () => process.exit(3)).on('error', error => {
    if (!['DEPTH_ZERO_SELF_SIGNED_CERT', 'SELF_SIGNED_CERT_IN_CHAIN', 'UNABLE_TO_VERIFY_LEAF_SIGNATURE'].includes(error.code)) process.exit(4);
    console.log('Trusted CA accepted; untrusted certificate rejected.');
  });
}).on('error', () => process.exit(5));
""",
    ]
    subprocess.run(command, check=True, timeout=45)
    result = subprocess.run(
        [
            "kubectl",
            "auth",
            "can-i",
            "get",
            "secrets",
            "--all-namespaces",
            "--as=system:serviceaccount:backstage:backstage",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1 and result.stdout.strip() == "no", (
        "Backstage must not read cluster secrets."
    )
    print(
        "Stable identity, existing-account linking, destination rejection, and restricted cluster access verified."
    )

    verify_groups(token, api)


if __name__ == "__main__":
    main()
