"""Mount local CA trust and native Backstage integration config without committing secrets."""

import argparse
import getpass
import json
import os
import re
import subprocess

from bootstrap import STATE, secret


def apply(resource):
    # Server-side apply avoids duplicating secret values in last-applied annotations.
    result = subprocess.run(
        [
            "kubectl",
            "apply",
            "--server-side",
            "--field-manager=platform-local",
            "-f",
            "-",
        ],
        input=json.dumps(resource),
        text=True,
        capture_output=True,
    )
    if result.returncode:
        # API errors can echo submitted secrets; report only the resource identity.
        raise RuntimeError(f"Could not apply {resource['kind']}/{resource['metadata']['name']}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-owner")
    args = parser.parse_args()
    if args.github_owner is not None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", args.github_owner):
            raise SystemExit("Provide a GitHub username or organization.")
        token = getpass.getpass("Dedicated GitHub publishing token (hidden): ").strip()
        if not token:
            raise SystemExit("No token supplied; GitHub configuration was not changed.")
        STATE.mkdir(exist_ok=True)
        path = STATE / "backstage-integrations.json"
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(
                {"integrations": {"github": [{"host": "github.com", "token": token}]}},
                handle,
            )
        (STATE / "github-owner").write_text(args.github_owner + "\n")
        print(
            "GitHub settings saved locally. Run make portal-up to activate the three GitHub templates."
        )
        return
    apply({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "backstage"}})
    ca = secret("default", "idpbuilder-cert")["ca.crt"]
    apply(
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "platform-ca", "namespace": "backstage"},
            "data": {"ca.crt": ca},
        }
    )
    (STATE / "platform-ca.crt").write_text(ca)
    path = STATE / "backstage-integrations.json"
    config = json.loads(path.read_text()) if path.exists() else {}
    if set(config) - {"integrations"}:
        raise SystemExit("backstage-integrations.json may only contain native integrations config.")
    apply(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "platform-integrations", "namespace": "backstage"},
            "stringData": {"integrations.json": json.dumps(config)},
        }
    )
    print(
        "Local CA and native integration config are ready; External Secrets manages the session key."
    )


if __name__ == "__main__":
    main()
