"""Assemble pinned CNOE packages and this toolkit's three Backstage templates."""

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from image import IMAGE

ROOT = Path(__file__).resolve().parent
TOOLKIT = ROOT.parent
sys.path.insert(0, str(TOOLKIT))
STATE = ROOT / ".local"
STACKS_REF = "32160ecb5942b6d0199b1cef039cc3457d2b1100"
TOOLKIT_REF = "2e8ba04fd61e06ff92afae938156690aaa6ec5a9"
BASE_URL = "https://cnoe.localtest.me:8443/gitea"
PACKAGES = ("external-secrets", "keycloak", "backstage", "backstage-templates")


def template_values():
    from scaffold.new_repo import parse_set

    return {
        "OWNER": "platform-engineering",
        "AWS_REGION": "eu-central-1",
        "TOOLKIT_REPOSITORY": "ersahinco/developer-platform-kit",
        "TOOLKIT_REF": TOOLKIT_REF,
    } | parse_set(shlex.split(os.environ.get("PORTAL_SET", "")))


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
    from scaffold.backstage import export

    values = template_values()
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
        fixed_values=values,
        github_settings=(
            json.loads((STATE / "github-settings.json").read_text())
            if (STATE / "github-settings.json").exists()
            else None
        ),
    )
    (entities / "organization").mkdir()
    (entities / "organization/platform.yaml").write_text(
        json.dumps(
            {
                "apiVersion": "backstage.io/v1alpha1",
                "kind": "Group",
                "metadata": {"name": values["OWNER"]},
                "spec": {"type": "team", "children": []},
            },
            indent=2,
        )
        + "\n"
    )
    location = entities / "catalog-info.yaml"
    catalog = json.loads(location.read_text())
    catalog["spec"]["targets"].append("./organization/platform.yaml")
    location.write_text(json.dumps(catalog, indent=2) + "\n")
    # idpbuilder publishes this generated staging tree to its local Gitea.
    # Keep the pinned checkout untouched; only explicit overlays/patches change the output.
    for package in PACKAGES:
        directory = "entities" if package == "backstage-templates" else "manifests"
        shutil.copyfile(upstream / "LICENSE", target / package / directory / "LICENSE")
    shutil.copyfile(ROOT / "applications/kustomization.yaml", target / "kustomization.yaml")
    result = subprocess.run(
        ["kubectl", "kustomize", str(target)], check=True, capture_output=True, text=True
    )
    (target / "backstage.yaml").write_text(result.stdout)
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
                        "path": "/spec/template/metadata/annotations/platform.local~1integrations-hash",
                        "value": digest,
                    }
                ]
            ),
        }
    )
    path.write_text(json.dumps(overlay, indent=2) + "\n")
    subprocess.run(["kubectl", "kustomize", str(manifests)], check=True, stdout=subprocess.DEVNULL)
    # Standard patch application fails if the pinned upstream context changes.
    subprocess.run(["git", "apply", str(ROOT / "keycloak/setup.patch")], cwd=target, check=True)
    keycloak = target / "keycloak/manifests"
    (keycloak / "kustomization.yaml").write_text(
        json.dumps({"resources": sorted(path.name for path in keycloak.glob("*.yaml"))}) + "\n"
    )
    subprocess.run(["kubectl", "kustomize", str(keycloak)], check=True, stdout=subprocess.DEVNULL)
    print(f"Prepared {len(PACKAGES)} CNOE packages and three templates in {target}")


if __name__ == "__main__":
    main()
