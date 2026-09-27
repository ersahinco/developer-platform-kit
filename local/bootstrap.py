"""Prepare the local Git organization and wait for its Argo applications."""

import base64
import json
import os
import re
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.parse import unquote, urlencode, urlsplit
import ssl
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import (
    Request,
    urlopen,
    build_opener,
    HTTPSHandler,
    HTTPCookieProcessor,
)

from prepare import BASE_URL, STATE

PORTAL = "https://cnoe.localtest.me:8443"

os.environ["KUBECONFIG"] = str(STATE / "kubeconfig")


def secret(namespace, name):
    result = subprocess.run(
        ["kubectl", "get", "secret", name, "-n", namespace, "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        key: base64.b64decode(value).decode()
        for key, value in json.loads(result.stdout)["data"].items()
    }


def context():
    return ssl.create_default_context(cadata=secret("default", "idpbuilder-cert")["ca.crt"])


def request(url, *, headers=None, data=None, method=None):
    req = Request(url, headers=headers or {}, data=data, method=method)
    with urlopen(req, context=context(), timeout=30) as response:
        body = response.read()
        return json.loads(body) if body else None


class LoginForm(HTMLParser):
    action = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("id") == "kc-form-login":
            self.action = attrs["action"]


def login(username="user1"):
    opener = build_opener(HTTPSHandler(context=context()), HTTPCookieProcessor(CookieJar()))
    query = urlencode({"env": "development", "origin": PORTAL, "scope": "openid profile email"})
    with opener.open(PORTAL + "/api/auth/keycloak-oidc/start?" + query, timeout=30) as response:
        form = LoginForm()
        form.feed(response.read().decode())
    if (
        not form.action
        or urlsplit(form.action).netloc != urlsplit(PORTAL).netloc
        or urlsplit(form.action).scheme != "https"
    ):
        raise RuntimeError("Expected the local Keycloak sign-in form.")
    credentials = secret("keycloak", "keycloak-config")
    data = urlencode(
        {
            "username": username,
            "password": credentials["USER_PASSWORD"],
            "credentialId": "",
        }
    ).encode()
    with opener.open(form.action, data=data, timeout=30) as response:
        body = response.read().decode()
    match = re.search(r"decodeURIComponent\('([^']+)'\)", body)
    if not match:
        raise RuntimeError("Keycloak did not return the Backstage sign-in callback.")
    result = json.loads(unquote(match[1]))
    return result["response"]["backstageIdentity"]["token"]


def main():
    credentials = secret("gitea", "gitea-credential")
    headers = {
        "Authorization": "token " + credentials["token"],
        "Content-Type": "application/json",
    }
    try:
        request(BASE_URL + "/api/v1/orgs/platform", headers=headers)
    except HTTPError as error:
        if error.code != 404:
            raise
        request(
            BASE_URL + "/api/v1/orgs",
            headers=headers,
            data=json.dumps({"username": "platform", "visibility": "private"}).encode(),
        )
    # idpbuilder can return before Argo observes the new Git revision.
    for name, repo in (
        ("backstage", "backstage-manifests"),
        ("backstage-templates", "backstage-templates-entities"),
    ):
        revision = request(
            BASE_URL + f"/api/v1/repos/giteaAdmin/idpbuilder-toolkit-{repo}/branches/main",
            headers=headers,
        )["commit"]["id"]
        deadline = time.monotonic() + 240
        while True:
            result = subprocess.run(
                ["kubectl", "get", "application", name, "-n", "argocd", "-o", "json"],
                check=True,
                capture_output=True,
                text=True,
            )
            status = json.loads(result.stdout).get("status", {})
            if (
                status.get("sync", {}).get("revision") == revision
                and status.get("sync", {}).get("status") == "Synced"
                and status.get("health", {}).get("status") == "Healthy"
            ):
                break
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"{name} has not completed rollout of {revision}; inspect make portal-status."
                )
            time.sleep(3)
    print(
        "Local platform is synced and healthy. Templates refresh through the catalog processing loop; allow about a minute."
    )


if __name__ == "__main__":
    main()
