# Runtime Toolkit

Use this doc when evaluating or adding a runtime target such as local Compose,
AWS/ECS, Kubernetes, or a future provider-edge integration backed by a real
workload need.
Goal: prove the runtime can satisfy the workload contract without moving
provider assumptions into app code.

Use with:

- [Platform Contract](platform-contract.md): portable workload rules
- [Runtime Defaults](runtime-defaults.md): blessed runtime and capability defaults
- [Architecture](architecture.md): repo and ownership boundaries
- [Platform Capabilities](platform-capabilities.md): current capability map

`platform/workloads.json` is the machine-readable workload contract.
`platform/runtime-defaults.json` is the machine-readable runtime-default map.
`platform/runtime-conformance.json` is the local/CI runtime proof fixture.
`make runtime-conformance` is the main executable proof.

The stable center stays the same:

- the workload contract defines workload intent
- the platform catalog provides reusable capabilities
- runtime targets realize the contract at the platform edge

The delivery toolkit standardizes developer-facing app host conventions, local
proof, build/test checks, delivery evidence, and infra ownership boundaries. It
does not replace managed app runtimes, servers, or Kubernetes; it gives them a
clear workload contract to realize.

## Entry Criteria

- There is a concrete reason: cost, reliability, capability, or region/account need.
- Local development remains fast enough to be the default inner loop.
- `packages/domain` and `packages/application` do not need provider imports or runtime-specific knowledge.
- Existing workloads keep the same portable contract unless every runtime should support new behavior.

Do not add a runtime target just to prove portability.

For now, AWS is the only reviewed cloud runtime in this repo. Managed database,
DNS, edge, identity, or storage providers stay on the horizon until a workload
has a concrete need and clear runtime ownership.

Local Kubernetes is now the first richer local proof runtime target. Future
production Kubernetes remains out of scope until app teams, data science, batch,
GPU, Spark, or ML/AI workloads need capabilities the current targets do not
provide and a runtime owner accepts the platform surface. That decision still
starts with the workload contract and runtime owner; it does not replace the
stable center with Helm, CRDs, or a platform control plane.

## Runtime Families

Use these families to talk about runtime options without making them active
targets prematurely:

| Family | Status in this repo | Examples | Useful for |
|---|---|---|---|
| Local proof runtimes | `local-compose` and `local-kubernetes` active | Docker Compose, kind | fast developer proof; richer local network, storage, compute, probes, jobs, sidecars, and policy checks when Compose is too small |
| Managed app runtimes | `aws-ecs` active production target; others are future options | ECS/Fargate, Lambda, Azure Functions, Cloud Run, Azure Container Apps, App Runner | teams that want to deploy workloads into owned managed runtimes without building a substrate platform |
| Owned substrate runtimes | not active | EC2 or VM fleets, on-prem servers, self-managed Kubernetes, managed Kubernetes | cases where the platform team owns ingress, node/runtime posture, storage classes, identity mapping, policy, observability, upgrades, and runbooks |

Managed Kubernetes sits in the owned-substrate family for this toolkit. EKS,
AKS, or GKE may manage the control plane, but the platform still owns much of
the runtime surface: ingress, storage classes, IAM or workload identity mapping,
network policy, observability routing, node/runtime posture, admission policy,
upgrade rhythm, failure modes, and runbooks.

## Runtime Must Provide

- OCI image execution with immutable revisions and non-root users
- networking, DNS, ingress, and dependency routing
- short-lived delivery identity and least-privilege runtime identity
- secret injection without baking values into images or artifacts
- Prometheus-compatible metrics, Loki-compatible logs, and OTLP/HTTP traces when enabled
- one-off and scheduled jobs using the same image, config, secrets, and evidence shape
- immutable rollout, explicit rollback categories, and portable release evidence
- separate bootstrap/platform and app/runtime ownership

It must also preserve workload classes:

- externally routed edge services
- internal long-running services
- manually triggered operator jobs
- scheduler-triggered recurring jobs

## Current Runtime Targets

`local-compose` is the local-first runtime for fast iteration. It uses Docker
Compose, local Postgres/PgBouncer, Redis-backed Dapr pub/sub, and the OSS
observability stack to prove the workload contract before cloud deployment.

`local-kubernetes` is the richer local proof runtime. It uses kind, kubectl,
static Kubernetes manifests, Services, probes, ConfigMaps, Secrets, Jobs, and
PersistentVolumeClaims to prove selected workload boundaries without cloud
Kubernetes machinery.

`aws-ecs` is the current reviewed production runtime. It realizes the same
contract with ECS/Fargate, ALB/WAF, RDS, SNS/SQS behind Dapr, S3, EventBridge
Scheduler, IAM, and CloudWatch.

Runtime defaults are intentionally opinionated. Local Compose uses local
identity, local secret injection, and the OSS observability stack. AWS/ECS uses
ECS task roles, GitHub OIDC for delivery, Secrets Manager or SSM injection, and
runtime-edge observability routing. Future enterprise choices such as Okta,
Kong, OPA, Splunk, or Datadog belong in a runtime profile or runtime catalog,
not in per-workload metadata.

A provider-edge integration can still be documented as a future option, but it
should not appear as an active runtime target until there is a real workload,
reviewed ownership, and delivery path.

A workload can still be real and live under `apps/` before it is admitted to a
cloud runtime. Local support through `local-compose` is a valid first runtime
target, not a reason to demote the host into `examples/`.

Future production runtimes become active only when they have a real workload
need, an owner, a config surface, conformance, evidence, failure modes, and a
runbook. Until then, keep them as taxonomy or candidate guidance rather than
adding runtime inventory, workload admission, or catalog branches.

## Foreign Workload Evaluation

Use this path when an existing internal workload already runs through
team-owned AWS account wiring, Terraform, Jenkins or Azure DevOps, Datadog or
Splunk, nonstandard DNS, an externally managed PostgreSQL database, and its own
runbooks. The useful test is whether the workload can fit the delivery toolkit
without forcing the stable center to absorb platform-edge details.

Draft one workload JSON object outside the repo, then run:

```bash
WORKLOAD_CANDIDATE=/tmp/payments-gateway.json make workload-fit-check
```

Keep only workload identity and intent in the candidate:

```json
{
  "name": "payments_gateway",
  "kind": "service",
  "use_cases": ["internal-api", "connector"],
  "owner": "payments-platform",
  "runtime": {
    "supported": ["local-compose"],
    "admitted": []
  },
  "operational": {
    "class": "internal-service",
    "exposure": "internal"
  },
  "service": {
    "port": 8080
  },
  "image": {
    "repository": "payments-gateway",
    "package": "payments-gateway",
    "command": "python -m payments_gateway.main"
  },
  "metrics": {
    "format": "prometheus",
    "required_names": ["workload_info"]
  },
  "traces": {
    "supported": false
  },
  "database": {
    "semantics": "postgresql",
    "pooling": "direct"
  },
  "config": {
    "env": ["DATABASE_URL", "DB_HOST", "DB_PORT", "DB_USER", "DB_NAME"],
    "secrets": ["DB_PASSWORD"]
  }
}
```

Account IDs, DNS names, externally managed database endpoints, IAM roles,
Jenkins or Azure DevOps pipelines, Datadog or Splunk routing, log indexes,
Terraform resources, incident practices, and runbook links stay at the
platform edge. Release evidence, operator payloads, and incident evidence still
correlate through workload id, run id, image tag, timestamp, status, and
runtime identifiers.

After a candidate fits, use the normal discovery and validation path:

```bash
make platform-doctor
make workload-readiness
make workload-readiness-check
make platform-toolkit-validate-local
make platform-toolkit-validate-cloud
```

## AWS ECS Target

The current `aws-ecs` target is implemented through `infra/`,
`.github/workflows/`, `scripts/`, `platform/concerns/`, tests, and docs.

- AWS details stay in `infra/platform`, `infra/app`, and AWS-facing scripts.
- The portable part is the workload contract and evidence.
- `platform/workloads.json` remains the workload contract across runtime targets.
- `platform/runtime-conformance.json` stays runtime-check-specific; do not grow it into a second workload contract.

Inspection commands:

```bash
make workload-capability-matrix
make capability-implementation-matrix
make candidate-capability-matrix
make adapter-seam-matrix
make capability-proof-local
make capability-proof-local-live
make capability-proof-cloud
```

For current AWS rollout and operator flow, use [Deployment](deployment.md).

## Portable Baseline

| Area | Status |
|---|---|
| Application core | Portable |
| Workload contract | Portable shape |
| Data and database | PostgreSQL-compatible shape |
| Local runtime | First-class contract proof |
| Observability baseline | Mostly OSS-portable |
| Incident and release evidence | Portable shape |
| Cloud runtime implementation | Intentionally AWS-specific |

## Adapter Strategy

Prefer portability through explicit adapters and replacement seams:

- keep business behavior in `packages/domain` and `packages/application`
- keep database, pub/sub, storage, and HTTP client adapters in `packages/infrastructure`
- keep runtime-target realization in `infra/`, workflows, and scripts
- use the capability matrices and proof commands before adding a new target, so active seams, candidate-only choices, evidence, and live local behavior stay visible

For this repo today:

- PostgreSQL behavior is the portable database contract; RDS is the current realization
- Dapr pub/sub is the app-facing eventing contract; SNS/SQS is the current realization
- workload config and secret names are portable; ECS task/env wiring is the current realization

## Current Gaps

- CI-to-Loki publishing is ready but inactive
- AWS-managed resource metrics still rely on CloudWatch at the platform edge
- no additional production runtime target is implemented yet
- local Kubernetes covers selected proof workloads only
- live kind validation is local/manual; CI currently protects static
  local-kubernetes contracts and capability evidence
- infra rollback remains reviewed plan/apply, not a permanent drill workflow

## Implementation Steps

1. Document the runtime reason.
2. Add explicit `infra/` ownership boundaries and catalog parts first.
3. Implement networking, identity, secrets, ingress, observability, job, and rollout behavior at the platform edge.
4. Keep app/domain/application code unchanged unless the portable contract itself must grow.
5. Run `make runtime-conformance` and the normal workflow, docs, and Terraform checks.

## Exit Criteria

- distinct bootstrap/platform and app/runtime roots
- declared workload images pass `make runtime-conformance`
- incident and release evidence stay recognizable across deploy and rollback
- existing workload intent remains recognizable without reinvention
- provider names stay out of `packages/domain`, `packages/application`, and workload business behavior
