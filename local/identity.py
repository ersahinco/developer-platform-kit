"""Configure native Keycloak account linking; OAuth secrets are prompted, never logged."""

import argparse
import getpass
import json
from urllib.parse import urlencode

from bootstrap import PORTAL, request, secret


def admin():
    credentials = secret("keycloak", "keycloak-config")
    token = request(
        PORTAL + "/keycloak/realms/master/protocol/openid-connect/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=urlencode(
            {
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": "cnoe-admin",
                "password": credentials["KEYCLOAK_ADMIN_PASSWORD"],
            }
        ).encode(),
    )["access_token"]

    def api(path, data=None, method=None):
        return request(
            PORTAL + "/keycloak/admin/realms/cnoe/" + path,
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
            },
            data=json.dumps(data).encode() if data is not None else None,
            method=method,
        )

    return api


def prepare(api):
    # Allow the standard profile scope requested by Backstage's OIDC provider.
    client = api("clients?clientId=backstage")[0]["id"]
    profile = next(scope for scope in api("client-scopes") if scope["name"] == "profile")
    api(f"clients/{client}/default-client-scopes/{profile['id']}", method="PUT")
    alias = "platform-existing-user"
    if not any(flow["alias"] == alias for flow in api("authentication/flows")):
        api("authentication/flows/first%20broker%20login/copy", {"newName": alias})
    path = f"authentication/flows/{alias}/executions"
    for execution in api(path):
        if execution.get("providerId") in {
            "idp-create-user-if-unique",
            "idp-confirm-link",
            "idp-email-verification",
        }:
            execution["requirement"] = "DISABLED"
            api(path, execution, "PUT")
    return alias


def groups(api):
    # These two demo accounts are managed by this local bootstrap only.
    managed = {"user1": "scaffold-creators", "user2": "scaffold-viewers"}
    for name in managed.values():
        if not any(g["name"] == name for g in api("groups")):
            api("groups", {"name": name})
    ids = {g["name"]: g["id"] for g in api("groups")}
    for username, group in managed.items():
        user = api(f"users?username={username}&exact=true")[0]["id"]
        for name in managed.values():
            api(
                f"users/{user}/groups/{ids[name]}",
                method="PUT" if name == group else "DELETE",
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=["prepare", "github", "google", "microsoft"])
    args = parser.parse_args()
    api = admin()
    flow = prepare(api)
    if args.provider == "prepare":
        groups(api)
        print("Stable identity, existing-account linking, and two scaffold groups are ready.")
        return
    alias = "platform-" + args.provider
    print(f"Register this callback: {PORTAL}/keycloak/realms/cnoe/broker/{alias}/endpoint")
    client_id = input("OAuth client ID: ").strip()
    client_secret = getpass.getpass("OAuth client secret (hidden): ").strip()
    if not client_id or not client_secret:
        raise SystemExit("Client ID and secret are required; provider was not changed.")
    provider = {
        "alias": alias,
        "displayName": args.provider.title(),
        "providerId": args.provider,
        "enabled": True,
        "trustEmail": False,
        "storeToken": False,
        "firstBrokerLoginFlowAlias": flow,
        "config": {
            "clientId": client_id,
            "clientSecret": client_secret,
            "syncMode": "IMPORT",
        },
    }
    existing = api("identity-provider/instances")
    path = "identity-provider/instances"
    if any(p["alias"] == alias for p in existing):
        api(path + "/" + alias, provider, "PUT")
    else:
        api(path, provider)
    print(
        "Provider configured. Complete browser sign-in and reauthenticate as an existing local user to link it."
    )


if __name__ == "__main__":
    main()
