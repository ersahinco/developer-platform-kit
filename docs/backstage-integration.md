# Backstage Integration

This repository is an importable Backstage catalog and action pack. It does not
fork Backstage or add a custom plugin.

Backstage provides discovery and operator UX. GitHub Actions remains the only
mutation gateway, Terraform remains the infrastructure and authoritative DNS
owner, and release evidence remains the observed deployment record.

## Install The Upstream Capability

In the self-hosted Backstage deployment, install the official GitHub Software
Templates action module:

```bash
yarn --cwd packages/backend add @backstage/plugin-scaffolder-backend-module-github
```

Register it in the Backstage backend:

```ts
backend.add(import('@backstage/plugin-scaffolder-backend-module-github'));
```

Configure the catalog from Git and make production catalog mutation read-only:

```yaml
catalog:
  readonly: true
  locations:
    - type: url
      target: https://raw.githubusercontent.com/ersahinco/aws-sdlc-containers/main/catalog-info.yaml
scaffolder:
  defaultEnvironment:
    parameters:
      deliveryRepoUrl: github.com?owner=ersahinco&repo=aws-sdlc-containers
```

The single `deliveryRepoUrl` environment parameter keeps templates reusable
without letting users select an arbitrary repository. Set it to the fork or
platform repository owned by that Backstage installation.

The Backstage GitHub App needs repository content read access and Actions write
access for that repository. It does not need provider credentials.
Restrict Software Template execution to the platform operator group with the
Backstage permission framework.

## Native Action Surface

The catalog exposes one native Backstage template for every manual app, infra,
and data workflow:

| Lane | Backstage action | GitHub workflow |
|---|---|---|
| App | build workload images | `app-build.yml` |
| App | deploy approved workload images | `app-deploy.yml` |
| Infra | plan infrastructure | `infra-plan.yml` |
| Infra | apply reviewed plans | `infra-apply.yml` |
| Data | apply schema phase | `data-schema-apply.yml` |
| Data | switch runtime modes | `data-runtime-switch.yml` |
| Data | run backfill | `data-backfill.yml` |
| Data | promote support jobs | `data-support-deploy.yml` |
| Data | capture operational snapshot | `operational-snapshot.yml` |

Each action calls `github:actions:dispatch` against the default branch.
Existing workflow confirmation, immutable-image, plan lineage, environment,
OIDC, dry-run, and release-evidence gates still apply. The Backstage forms
default cloud-changing actions to dry-run.

Run the contract check after changing a form or workflow:

```bash
uv run pytest tests/contracts/test_backstage_catalog_contract.py -q
make monorepo-capability-profile-check
```

## Placement And Evidence

`make monorepo-capability-profile` is the compact machine-readable projection
for Backstage or another developer-facing UI. It includes:

- supported, admitted, default, and reference runtime targets per workload;
- the Backstage action mapped to each GitHub workflow;
- the source-of-truth owner for every mutable concern;
- the Coolify and NetBird candidate status.

Placement is intentionally policy, not a claim of live state. A supported
target has a contract proof; an admitted target has reviewed runtime ownership.
Only release evidence establishes that a particular workload digest was
deployed to a particular runtime.

## Platform-Edge Products

Coolify and NetBird appear in the catalog so teams can discover their role and
gate without treating them as installed platform dependencies.

- Coolify is an application-delivery candidate for the Hetzner reference. It
  has no mutation authority unless the complete ADR 0003 experiment passes and
  it replaces the direct operator path.
- NetBird is a private-network candidate for a real cross-site dependency. It
  never owns public authoritative DNS. If admitted, its groups, policies,
  routes, and split-DNS configuration must be IaC-owned and evidence-producing.

No generic adapter is provided. An admitted integration should call the
product's documented API or Terraform provider from a protected GitHub
workflow and preserve the workload and evidence contracts.
