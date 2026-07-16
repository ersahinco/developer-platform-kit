# ADR 0004: Use Backstage As The Governed Integration Front Door

## Status

Accepted on 2026-07-16

## Context

The delivery toolkit already uses GitHub Actions for app, infrastructure, and
data delivery; Terraform for infrastructure and DNS; a workload contract and
platform catalog for portable intent; and release events for runtime evidence.
Backstage, Coolify, and NetBird can add useful product surfaces, but allowing
each product to become an independent writer would create drift and duplicate
the repository's existing policy.

The desired product is not another orchestrator. It is a self-hostable
developer-facing integration of established open-source tools with explicit
ownership, review, portability, and evidence boundaries.

## Decision

Use Backstage as an optional, self-hosted **read-and-dispatch front door** over
the stable center:

- ingest the repository's standard Backstage entities from
  `catalog-info.yaml`;
- expose the native Backstage Software Templates in `catalog/action-*.yaml`;
- dispatch only the existing GitHub Actions workflows through the upstream
  `github:actions:dispatch` action;
- keep all provider credentials, approvals, environments, and OIDC identities
  in GitHub Actions;
- derive workload placement policy from
  `platform/workload-runtime-support.json`;
- treat release evidence as the observed deployment record rather than
  claiming that catalog admission proves a live deployment.

Mutable concerns retain one authority:

| Concern | Authority |
|---|---|
| Workload identity | `platform/workloads.json` |
| Runtime support and admission | `platform/workload-runtime-support.json` |
| Runtime defaults | `platform/runtime-defaults.json` |
| App, infra, and data mutation | GitHub Actions |
| Infrastructure and authoritative public DNS | Terraform roots under `infra/` |
| Runtime configuration | Git and the admitted runtime realization |
| Observed release/deployment state | `scripts/observability/release_event.py` artifacts |
| Catalog and action UX | Backstage read model; no provider credentials |

The generated monorepo capability profile exposes these authorities, delivery
actions, placement policy, and platform-edge candidates. Contract tests keep
the Backstage action inputs equal to each workflow's real
`workflow_dispatch` inputs.

Coolify and NetBird are cataloged platform-edge candidates, not active
dependencies:

- **Coolify** may replace the direct Hetzner delivery layer only after the
  disposable ADR 0003 gate proves exact-digest deployment and rollback, Dapr,
  fresh jobs, recovery, evidence, and meaningful code deletion.
- **NetBird** may own private peer connectivity, access policy, routes, and
  split DNS only after a concrete cross-site workload proof. Terraform remains
  authoritative for public DNS. Admission requires IaC-owned policy, bounded
  setup-key handling, reachability and denial evidence, recovery, and a named
  operator.

Do not add a custom Backstage plugin, generic product adapter, workflow
composer, or new platform API for these integrations. Use the upstream
Backstage GitHub action and each product's public API or Terraform provider
only when an admitted proof needs it.

## Security Boundary

- Backstage receives a GitHub identity able to read this repository and
  dispatch its workflows; it receives no AWS, Cloudflare, Hetzner, Supabase,
  Coolify, NetBird, registry, database, or object-storage credential.
- GitHub environment protection and workflow confirmation gates remain
  authoritative even when a run starts in Backstage.
- Template execution is restricted to the platform operator group in the
  Backstage permission framework.
- The Backstage catalog is configured read-only in production; Git and the
  existing metadata files remain canonical.
- Coolify and NetBird tokens, if later admitted, live in protected GitHub
  environments and are scoped to the smallest team/account and action set.

## Consequences

- Application developers get one catalog and action surface without learning
  provider credentials or direct runtime mutation paths.
- Platform developers keep standard GitHub, Terraform, Compose, Backstage, and
  evidence interfaces rather than maintaining a private framework.
- A self-hosted Backstage deployment still needs normal authentication,
  database, backup, patching, and authorization ownership; this repository
  intentionally ships an importable catalog/action pack instead of a forked
  Backstage distribution.
- The catalog describes placement policy and evidence links. Live inventory
  remains runtime evidence and is not inferred from supported or admitted
  targets.
- Coolify and NetBird remain replaceable platform-edge choices and can be
  rejected without changing the stable center.

## Upstream Boundaries

- Backstage Software Templates and the native GitHub action module:
  [templates](https://backstage.io/docs/features/software-templates/writing-templates/),
  [built-in action modules](https://backstage.io/docs/features/software-templates/builtin-actions/).
- GitHub workflow dispatch and OIDC:
  [workflow dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event),
  [OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-with-reusable-workflows).
- Coolify team-scoped API and deployment events:
  [authorization](https://coolify.io/docs/api-reference/authorization),
  [start application](https://coolify.io/docs/api-reference/api/applications/start-application-by-uuid),
  [webhook payloads](https://coolify.io/docs/knowledge-base/webhook-payloads).
- NetBird self-hosting, API, setup keys, and DNS:
  [self-hosting](https://docs.netbird.io/selfhosted/selfhosted-guide),
  [API](https://docs.netbird.io/api/introduction),
  [setup keys](https://docs.netbird.io/api/resources/setup-keys),
  [DNS](https://docs.netbird.io/api/resources/dns).
