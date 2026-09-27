"""Assemble pinned CNOE packages and this toolkit's three Backstage templates."""

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from image import IMAGE

ROOT = Path(__file__).resolve().parent
TOOLKIT = ROOT.parent
STATE = ROOT / ".local"
STACKS_REF = "32160ecb5942b6d0199b1cef039cc3457d2b1100"
TOOLKIT_REF = "1e9e21e755970c4aa1100683a2f366b65af75684"
BASE_URL = "https://cnoe.localtest.me:8443/gitea"
PACKAGES = ("external-secrets", "keycloak", "backstage", "backstage-templates")


def main():
    if not (TOOLKIT / "scaffold/backstage.py").is_file():
        raise SystemExit(f"Expected toolkit checkout at: {TOOLKIT}")
    STATE.mkdir(exist_ok=True)
    upstream = STATE / "stacks"
    if not upstream.exists():
        subprocess.run(
            ["git", "clone", "https://github.com/cnoe-io/stacks.git", str(upstream)],
            check=True,
        )
    subprocess.run(["git", "-C", str(upstream), "checkout", "--detach", STACKS_REF], check=True)
    target = STATE / "packages"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir()
    for package in PACKAGES:
        source = upstream / "ref-implementation" / package
        shutil.copytree(source, target / package)
        shutil.copyfile(source.with_suffix(".yaml"), (target / package).with_suffix(".yaml"))
    entities = target / "backstage-templates/entities"
    shutil.rmtree(entities)
    sys.path.insert(0, str(TOOLKIT))
    from scaffold.backstage import export

    owner_path = STATE / "github-owner"
    owner = owner_path.read_text().strip() if owner_path.exists() else "platform"
    github = owner_path.exists()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner):
        raise SystemExit("github-owner must contain one GitHub username or organization.")
    if github and not (STATE / "backstage-integrations.json").exists():
        raise SystemExit("Configure .local/backstage-integrations.json before selecting GitHub.")
    export(
        entities,
        provider="github" if github else "gitea",
        base_url="https://github.com" if github else BASE_URL,
        allowed_owners=(owner,),
    )
    (entities / "organization").mkdir()
    (entities / "organization/platform.yaml").write_text(
        """
apiVersion: backstage.io/v1alpha1
kind: Group
metadata:
  name: platform-engineering
spec:
  type: team
  children: []
"""
    )
    location = entities / "catalog-info.yaml"
    catalog = json.loads(location.read_text())
    catalog["spec"]["targets"].append("./organization/platform.yaml")
    location.write_text(json.dumps(catalog, indent=2) + "\n")
    for template in entities.glob("*/template.yaml"):
        document = json.loads(template.read_text())
        properties = document["spec"]["parameters"][0]["properties"]
        for name, value in {
            "OWNER": "platform-engineering",
            "AWS_REGION": "eu-central-1",
            "TOOLKIT_REPOSITORY": "ersahinco/developer-platform-kit",
            "TOOLKIT_REF": TOOLKIT_REF,
        }.items():
            if name in properties:
                properties[name]["default"] = value
        template.write_text(json.dumps(document, indent=2) + "\n")
    # Argo removes obsolete generated ConfigMaps only after the replacement is healthy.
    application = target / "backstage.yaml"
    result = subprocess.run(
        [
            "kubectl",
            "patch",
            "--local",
            "-f",
            str(application),
            "--type=merge",
            "-p",
            json.dumps(
                {
                    "spec": {
                        "syncPolicy": {
                            "automated": {"prune": True},
                            "syncOptions": ["CreateNamespace=true", "PruneLast=true"],
                        }
                    }
                }
            ),
            "-o",
            "yaml",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    application.write_text(result.stdout)
    # Native Kustomize overlays preserve upstream resources without text rewriting.
    manifests = target / "backstage/manifests"
    shutil.copytree(ROOT / "config", manifests, dirs_exist_ok=True)
    path = manifests / "kustomization.yaml"
    overlay = json.loads(path.read_text())
    image_name, image_tag = IMAGE.split(":")
    overlay["images"] = [
        {
            "name": "ghcr.io/cnoe-io/backstage-app",
            "newName": image_name,
            "newTag": image_tag,
        }
    ]
    integration_file = STATE / "backstage-integrations.json"
    digest = hashlib.sha256(
        integration_file.read_bytes() if integration_file.exists() else b"{}"
    ).hexdigest()
    overlay["patches"].append(
        {
            "target": {"kind": "Deployment", "name": "backstage"},
            "patch": json.dumps(
                [
                    {
                        "op": "add",
                        "path": "/spec/template/metadata/annotations",
                        "value": {"platform.local/integrations-hash": digest},
                    }
                ]
            ),
        }
    )
    path.write_text(json.dumps(overlay, indent=2) + "\n")
    subprocess.run(["kubectl", "kustomize", str(manifests)], check=True, stdout=subprocess.DEVNULL)
    # Patch the pinned reference bootstrap: quiet secrets, native kubectl, resumable setup.
    job = target / "keycloak/manifests/keycloak-config.yaml"
    script = job.read_text().replace("set -ex -o pipefail", "set -e -o pipefail")
    download = 'curl -sS -LO "https://dl.k8s.io/release/v1.28.3//bin/linux/amd64/kubectl"\n              chmod +x kubectl'
    script = script.replace(download, "")
    script = script.replace(
        "              set +e",
        """              KUBECTL_URL="https://dl.k8s.io/release/v1.33.1/bin/linux/$(dpkg --print-architecture)/kubectl"
              curl -fsSLo kubectl "${KUBECTL_URL}"
              curl -fsSLo kubectl.sha256 "${KUBECTL_URL}.sha256"
              echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check
              chmod +x kubectl

              set +e""",
    )
    script = script.replace(
        'curl --fail-with-body -H "Authorization: bearer ${KEYCLOAK_TOKEN}"  "${KEYCLOAK_URL}/admin/realms/cnoe"  &> /dev/null',
        "./kubectl -n keycloak get secret keycloak-clients &> /dev/null",
    )
    job.write_text(script)
    print(f"Prepared {len(PACKAGES)} CNOE packages and three templates in {target}")


if __name__ == "__main__":
    main()
