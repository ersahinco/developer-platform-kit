# ADR 0003: Retain The Direct Hetzner Compose Reference

## Status

Accepted on 2026-07-16

## Context

The hybrid starter composes Cloudflare DNS, a Hetzner VM running Docker
Compose, Supabase PostgreSQL, AWS S3, and Dapr service invocation and pub/sub.
It is a reference runtime target; AWS/ECS remains the reviewed production
default.

Coolify, Portainer CE and BE, Kamal, Dokku, Dokploy, and CapRover were
evaluated as possible replacements or complements. Coolify is the closest
Compose-native delivery product, but its documented Compose path does not
support rolling updates and does not prove the reference's exact-digest
rollback, fresh one-off job, Dapr, and correlated evidence requirements.
Portainer is a fleet management plane rather than an application delivery
owner. The smaller deployment tools require the multi-image Dapr composition
to be restructured rather than removing it.

The replaceable operator plumbing is smaller than the project-specific
contract and evidence surface. Adding a privileged stateful control plane now
would increase recovery, patching, secret, and source-of-truth ownership
without a demonstrated starter-lane need.

## Decision

Retain the direct Terraform and Docker Compose implementation at `reference`
maturity. Freeze its operator surface: correctness, security, provider
compatibility, tests, and evidence may improve, but it must not grow fleet
management, a deployment UI, a generic product adapter, or a second control
plane.

The direct realization has one owner for each mutable concern:

| Concern | Owner |
|---|---|
| Infrastructure and DNS | Terraform in the isolated hybrid roots |
| Workload identity | `platform/workloads.json` |
| Runtime support and maturity | `platform/workload-runtime-support.json` |
| Image build and immutable digest | GitHub Actions App Build workflow |
| Image deployment | Explicit hybrid Make targets and operator script |
| Runtime configuration | Git-tracked Compose and Dapr files |
| Secret values | Approved external secret authority; the operator environment and host `.env` are delivery/runtime copies only |
| Origin TLS | Caddy on the runtime VM |
| Migrations and one-off jobs | Explicit fresh Compose containers |
| Rollback | Explicit prior digest, verification, and release evidence |
| Runtime state | Docker volumes on the starter VM and the named external data providers |
| Evidence | Project verifier and `scripts/observability/release_event.py` |
| Operator access | Restricted SSH and explicit Make targets |

Do not install Coolify and Portainer against this runtime or add either as a
second writer. Portainer Business Edition may be evaluated separately for a
real brownfield fleet that needs RBAC, audit, SSO, or disconnected operation;
it is not part of this runtime target.

## Product Adoption Gate

Before adding custom rollout, scheduling, secret-management, fleet, or UI
features, run a maximum two-business-day Coolify experiment outside the
repository against disposable infrastructure. The experiment must prove:

- deployment and inspection of the exact requested OCI digest without a build
- Git-owned Compose with no independent UI mutation
- one Dapr app/sidecar pair, invocation, pub/sub, and duplicate-event behavior
- a fresh migration or export container with meaningful exit status
- unproxied Terraform-owned DNS and origin ACME TLS
- health, readiness, metrics, structured logs, and S3 manifest integrity
- restoration of the exact previous digest after a failed deployment
- continued runtime availability while the control plane is unavailable
- backup and restoration of the control-plane database, application key, and
  SSH keys
- bounded Terraform destroy and correlated release evidence

Adopt the product only if it replaces the direct operator implementation,
deletes at least 180 existing lines, and needs no more than 100 new integration
lines. A failure retains this decision; it must not leave a parallel product
path in the repository.

## Decision Evidence

The product conclusions use primary documentation available on the research
date:

- Coolify supports Compose and prebuilt-image delivery, but excludes Compose
  from rolling updates and documents rollback in terms of images available on
  the server: [Compose](https://coolify.io/docs/knowledge-base/docker/compose),
  [rolling updates](https://coolify.io/docs/knowledge-base/rolling-updates),
  and [application rollback](https://coolify.io/docs/applications).
- Coolify recovery adds control-plane database, `APP_KEY`, and SSH-key backup
  responsibilities: [backup and restore](https://coolify.io/docs/knowledge-base/how-to/backup-restore-coolify).
- Kamal health-gates its application model, while accessories have a separate
  lifecycle: [deploy](https://kamal-deploy.org/docs/commands/deploy/) and
  [accessories](https://kamal-deploy.org/docs/configuration/accessories/).
- CapRover documents that its Compose parser supports only a subset of Compose
  fields: [Docker Compose](https://caprover.com/docs/docker-compose.html).

These sources establish product assistance and structural limits. The
project-specific digest, Dapr, job, data-integrity, recovery, and evidence
claims remain unknown until the bounded experiment proves them.

## Consequences

- Terraform, Git, the workload contract, and the evidence schema remain
  authoritative.
- The starter retains its single-VM availability limit, local Redis recovery
  limit, post-deploy verification, and manual rollback.
- No additional control-plane database, privileged agent, product backup, or
  license dependency is introduced.
- The repo continues to own the small direct deployment path and the larger
  project-specific Dapr, database, object-integrity, and evidence proofs.
- Compose, OCI digests, Terraform, and the evidence schema remain the exit
  boundaries for a future replacement.

## Reconsider When

- more than three independently operated starter servers need shared
  management;
- RBAC, SSO, audit, or disconnected edge operation becomes an owned
  requirement;
- rollout or recovery incidents demonstrate that the direct path is
  operationally inadequate;
- a product proves Compose health-gated rollout and exact-digest rollback; or
- the bespoke operator-only surface exceeds roughly 400 lines.
