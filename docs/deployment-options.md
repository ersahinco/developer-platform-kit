# Deployment Options

Decision guidance for greenfield and brownfield workload deployment choices.

This page is guidance, not an active runtime target. The stable center remains
the workload contract plus platform catalog. Deployment choices below are
runtime-target or platform-edge realization choices; they must not redefine
workload identity, add provider product fields to `platform/workloads.json`, or
turn the delivery toolkit into a provider abstraction layer.

Reviewed on 2026-06-16 against the current repo posture and the official AWS
and Supabase docs linked in [Sources](#sources).

## Current Default

Keep `aws-ecs` as the reviewed production runtime target for greenfield
workloads unless a real workload need says otherwise.

The current default is:

- `local-compose` for fast local proof
- `local-kubernetes` for richer local proof when Compose is too small
- `aws-ecs` for reviewed production realization
- ECS/Fargate compute plus AWS-managed dependencies as the paved road

That default already realizes the workload contract with ALB/WAF ingress,
private ECS placement, RDS/Postgres with PgBouncer, Dapr pub/sub backed by
SNS/SQS, S3, EventBridge Scheduler, CloudWatch/ADOT, GitHub OIDC, immutable
images, separated build/deploy and plan/apply, and release evidence.

For brownfield workloads, prefer fit before migration: draft the workload
contract, prove health/readiness/metrics/logs/config/secrets/idempotency
locally, then choose the smallest platform-edge connection that safely reaches
the existing system. Do not add a production runtime target until an owner,
conformance path, evidence artifact, failure-mode handling, and runbook exist.

## Decision Matrix

| Option | Greenfield fit | Brownfield fit | Strong when | Avoid when | Repo posture |
|---|---:|---:|---|---|---|
| ECS/Fargate compute plus AWS-managed dependencies | High | Medium | One AWS operations boundary, private RDS/SNS/SQS/S3, IAM, CloudWatch rollback/evidence | Team needs Supabase-specific product surface or existing DB must remain outside AWS | Recommended default |
| ECS/Fargate compute plus Supabase DB | Medium | Medium/High | Product team wants Supabase-managed Postgres, same-region AWS VPC, clear DB owner, PrivateLink or stable allowlist exists | Chatty low-latency SQL, strict single-control-plane ops, no owned pool/connection policy, no IPv4/IPv6 plan | Candidate platform-edge DB realization, not default |
| Compute elsewhere plus Supabase or AWS-managed dependencies | Low | Medium | Existing compute platform is owned and already emits equivalent image, secret, rollback, and evidence signals | Repo would need to bless another production runtime only to prove portability | Brownfield/candidate only |
| Brownfield app plus external systems/DB stay outside AWS | Low/Medium | High | Migration risk is in data ownership and network edges; workload can be wrapped by contract first | Attempting to centralize everything before proving behavior | Use workload-fit path; do not force migration |
| Scattered landscape across public internet, SaaS, AWS VPCs, and managed DBs | Medium | High | Use explicit edges: public TLS, allowlists, PrivateLink, VPN/DX/TGW, API gateway, async outbox | Shared hidden network assumptions, direct cross-system writes everywhere | Model as platform-edge connectivity patterns |

## Capability Impact

Deployment options are acceptable only when they realize the same workload
capabilities the current proof ladder already names. The product choice can
change at the platform edge; the capability evidence should stay recognizable.

| Capability | Workload-facing contract | Current `aws-ecs` realization | Hybrid or brownfield realization question |
|---|---|---|---|
| App host execution | OCI image, command, non-root runtime, health/readiness/metrics | ECS/Fargate service or run-task | Which owned runtime starts immutable images, exposes probes, and reports revision state? |
| Edge HTTP | `edge-service`, declared port, `/health`, `/ready`, `/metrics` | ALB/WAF to ECS tasks | Is the edge ALB, API Gateway, existing gateway, or external ingress, and who owns WAF/auth/routing evidence? |
| Relational database | PostgreSQL semantics, `DATABASE_URL` or `DB_*`, Liquibase, pooling intent | RDS PostgreSQL plus PgBouncer/direct paths | Is the database RDS, Supabase, or brownfield Postgres, and which endpoint/pool/restore owner is proven? |
| Async eventing | Dapr pub/sub, CloudEvents, outbox, idempotent consumer | Dapr sidecar backed by SNS/SQS | Does the runtime still hide broker mechanics behind Dapr, or is an API/outbox bridge safer for brownfield? |
| Object output | Stable object paths, manifests, artifact evidence | S3 data hub bucket | Which storage endpoint owns retention, integrity, access, and manifest evidence? |
| Scheduled execution | `scheduled-job`, rerun/idempotency, terminal event | EventBridge Scheduler plus ECS run-task | Which scheduler starts the same image with the same config/secrets and emits job evidence? |
| Operator job execution | `operator-job`, bounded rerun, structured terminal event | GitHub Actions reviewed ECS run-task | Which operator path provides review, identity, task context, logs, and payload artifacts? |
| Network connectivity | Exposure, private dependency reachability, egress identity when required | VPC subnets, security groups, ALB, endpoints/NAT as needed | Is the path public TLS/allowlist, PrivateLink, VPN/DX/TGW, VPC peering, or API gateway, and what proves it? |
| Secrets injection | Declared secret names, no baked values | ECS Secrets Manager or SSM injection | Which secret system injects values at runtime and how are rotations rolled forward? |
| Observability routing | Prometheus metrics, structured logs, optional OTLP traces | CloudWatch logs/alarms plus optional ADOT | How are CloudWatch, Supabase, SaaS, or brownfield signals correlated by request id, run id, image tag, and workload id? |
| Release evidence | Workflow run, image tag, runtime target, rollback category, verification | GitHub artifact release event | Which pipeline emits the same release event shape before the option is considered production-ready? |

Capability status:

- Active: `local-compose`, `local-kubernetes`, and `aws-ecs` capability rows in
  `platform/platform-inventory.json`.
- Candidate guidance: Supabase database realization, enterprise connectivity,
  compute elsewhere, external gateways, and brownfield databases.
- Out of scope until real need: new runtime targets, provider-neutral
  infrastructure modules, Helm/CRD machinery, portals, or per-workload provider
  fields.

If a deployment option cannot answer the hybrid or brownfield realization
question for every capability the workload uses, keep it as a candidate and
continue proving the workload locally.

## Decision Workflow

Use this order before changing runtime realization:

1. Classify the workload boundary in `platform/workloads.json`: operational
   class, exposure, config names, secret names, database need, Dapr need, and
   evidence.
2. Prove the workload locally with `local-compose`; add `local-kubernetes` only
   when Services, probes, Jobs, sidecars, rollout, or runtime injection are the
   risk.
3. For greenfield production, use `aws-ecs` unless a concrete workload need
   requires a different platform-edge realization.
4. For brownfield, keep the existing system or database in place first and
   prove the contract through a small connector, API boundary, or async outbox
   before migrating ownership.
5. For hybrid managed databases, choose the network path, pool mode, secret
   rotation, restore owner, and evidence before app deployment.
6. Promote anything to an active runtime target only after owner, conformance,
   evidence artifact, failure mode, delivery path, and runbook exist.

## Supabase DB With ECS Compute

Hybrid Supabase DB plus ECS/Fargate compute is logical when:

- Supabase is the chosen database product, not a portability demo.
- ECS remains the app host and delivery spine; Supabase remains a database
  platform-edge realization.
- The database is same-region or latency-tested, with PrivateLink preferred for
  sensitive steady-state traffic.
- The runtime edge chooses one pooler path: direct or session-safe connections
  for migrations and jobs; Supabase dedicated/shared pooler or app-side
  PgBouncer for request paths. Do not stack poolers by default.
- `DATABASE_URL`, `DB_*`, `/ready`, migrations, rollback, and evidence remain
  portable by boundary.

It is not logical when:

- The workload is latency-sensitive and transaction-heavy enough that
  cross-provider or public routing dominates user-visible behavior.
- The team needs AWS-native IAM, RDS Proxy, RDS alarms, backups, and restore as
  one operations surface.
- GitHub Actions or ECS cannot reach the correct Supabase endpoint because of
  IPv6/default direct endpoints, missing IPv4 add-on, missing NAT, or missing
  PrivateLink.
- Supabase Auth, Storage, or Realtime are assumed private through PrivateLink;
  as of the review date, Supabase documents PrivateLink for direct database and
  PgBouncer connections only.
- Compliance requires a single cloud control plane and unified audit or
  incident response.

Implementation rule: if Supabase is chosen, keep it out of
`packages/domain`, `packages/application`, and workload identity. The workload
contract stays PostgreSQL semantics; Supabase connection strings, network
restrictions, SSL settings, PrivateLink, and support-tier requirements belong
at the platform edge.

Candidate checklist:

| Check | Required answer before cloud mutation |
|---|---|
| Endpoint mode | Direct, session pooler, transaction pooler, or PrivateLink endpoint is named explicitly |
| IP family | IPv6, IPv4 add-on, or PrivateLink route is proven from the ECS runtime network |
| Pooling | Request path and job/migration path do not stack incompatible poolers |
| TLS | `sslmode=verify-full` and CA certificate handling are documented when SSL enforcement is enabled |
| Network controls | Allowlist or PrivateLink status is captured as evidence, including whether HTTPS APIs remain public |
| Ownership | Supabase project owner, AWS runtime owner, restore owner, and incident contact are named |
| Rollback | App image rollback, schema forward-fix/restore, and credential rotation paths are separated |
| Observability | CloudWatch, Supabase dashboard signals, pool metrics, and DB readiness are correlated by run id or request id |

## Networking Patterns

Use public TLS plus allowlists for low-sensitivity SaaS and early brownfield
proof. For ECS tasks in private subnets, this requires deliberate egress: NAT or
another controlled egress path, stable source IPs for allowlists, TLS
verification, and explicit Supabase IPv4/IPv6 handling.

Use Supabase PrivateLink or AWS PrivateLink when the dependency supports it,
traffic is steady or sensitive, and the VPC and managed service are in the
required region. This is the preferred steady-state pattern for
ECS-to-Supabase DB once Supabase plan, beta, account-sharing, and same-region
requirements are accepted.

Use Site-to-Site VPN, Direct Connect, and Transit Gateway for brownfield
estates with on-prem or many AWS VPCs. Prefer Transit Gateway when multiple
VPCs or networks need hub routing. Prefer Direct Connect when private,
predictable connectivity is worth the operational overhead. Use Site-to-Site
VPN for encrypted lower-barrier connectivity.

Use VPC peering for simple one-to-one AWS VPC connectivity with non-overlapping
CIDRs. Do not use it as a many-network transit strategy.

Use API Gateway or ALB as HTTP edges when the boundary is request/response,
auth, WAF, throttling, source-IP or VPC-endpoint policy, or private integration
to ECS/ALB. Use Dapr/outbox/async events when the boundary is cross-system
consistency, retries, replay, or migration safety.

## Failure Modes

Plan for these before cloud mutation:

- Latency and egress: cross-region or cross-provider SQL turns small queries
  into user-visible delay and can add NAT, Transit Gateway, Direct Connect,
  PrivateLink, or data-transfer costs.
- Connection limits: ECS scale-out, jobs, migrations, Supavisor/PgBouncer, and
  direct sessions must fit the database tier; transaction pooling can reject
  prepared-statement assumptions.
- Secrets: ECS-injected secrets need new tasks or deployments to refresh;
  Supabase DB password and certificate rotation need a rollout path.
- Identity: ECS task roles do not become Supabase database identity; database
  roles, passwords, row-level security, and audit need separate ownership.
- Rollback: app image rollback does not undo schema or external DB state;
  schema recovery remains forward-fix or restore by phase.
- Observability: CloudWatch and Supabase dashboards split the signal plane;
  evidence must capture DB endpoint mode, pool metrics, request latency, outbox
  depth, and correlation IDs.
- Compliance: confirm data region, backup/restore ownership, audit logs, SSL
  mode, PrivateLink status, support tier, and incident escalation.
- DNS/IP: Supabase direct DB endpoints are IPv6 by default; the IPv4 add-on is
  not dual-stack and can briefly disrupt direct connections during DNS
  reconfiguration.

## Proof Plan

Local proof:

- Keep the workload contract at PostgreSQL semantics, `DATABASE_URL`/`DB_*`,
  declared secrets, `/ready`, `/metrics`, structured logs, and Dapr/outbox when
  needed.
- Run the existing proof ladder: `make workload-readiness-local`,
  `make platform-toolkit-smoke-local`, `make dapr-smoke`, and
  `make local-kubernetes-evidence-drill` when sidecars, probes, rollout, or
  runtime injection matter.
- Add proof cases before cloud mutation: DB unreachable makes `/ready` fail, DB
  latency has timeouts, pool exhaustion is observable, migrations/jobs use
  direct or session-safe connections, and outbox replay is idempotent.

GitHub Actions proof:

- Preserve build before deploy and plan before apply:
  `make workflow-dry-run-validate-gh`, `make platform-toolkit-validate-cloud`,
  immutable image validation, and release evidence generation.
- For Supabase, prefer schema/app validation from the same runtime network path
  as ECS, not GitHub-hosted runners, unless IPv4/network restrictions explicitly
  support the runner path.
- CI should emit a non-mutating connectivity report before any cloud-changing
  workflow: DNS mode, TLS mode, endpoint type, allowlist or PrivateLink status,
  pool mode, and expected rollback category.

Before cloud mutation:

- Verify route path, source identity/IP, security groups, NAT, endpoint or
  PrivateLink, TLS `verify-full`, credentials, database role privileges, pool
  limits, and region.
- Review Terraform plan or provider-side change plan separately from app
  deployment.
- Confirm rollback target image, schema phase, external DB
  restore/forward-fix owner, and incident contact.

Evidence artifacts:

- Release event JSON/Markdown with workflow run ID, immutable image tag,
  runtime target, rollback category, and verification result.
- Network evidence: endpoint mode, resolved IP family, PrivateLink or allowlist
  status, source egress identity, and TLS certificate mode.
- Runtime evidence: `/health`, `/ready`, `/metrics`, latency sample, task
  revision, log group, alarm state, pool/client/backend connection counts, and
  outbox pending count.
- Data evidence: Liquibase/schema phase, migration output,
  backfill/export/operator terminal event, and restore/forward-fix notes for
  external database ownership.

## Sources

Repo anchors:

- [Runtime Defaults](runtime-defaults.md)
- [Platform Capabilities](platform-capabilities.md)
- [Proof Ladder](proof-ladder.md)
- [Data](data.md)
- [Runtime Toolkit](runtime-toolkit.md)
- [Deployment](deployment.md)

Official AWS docs:

- [Amazon ECS task networking options for Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html)
- [Amazon ECS deployment circuit breaker](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html)
- [AWS PrivateLink](https://docs.aws.amazon.com/vpc/latest/privatelink/what-is-privatelink.html)
- [AWS Transit Gateway](https://docs.aws.amazon.com/vpc/latest/tgw/what-is-transit-gateway.html)
- [AWS Direct Connect](https://docs.aws.amazon.com/directconnect/latest/UserGuide/Welcome.html)
- [AWS Site-to-Site VPN](https://docs.aws.amazon.com/vpn/latest/s2svpn/VPC_VPN.html)
- [VPC peering](https://docs.aws.amazon.com/vpc/latest/peering/what-is-vpc-peering.html)
- [API Gateway private integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-private.html)

Official Supabase docs:

- [Connecting to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Network Restrictions](https://supabase.com/docs/guides/platform/network-restrictions)
- [Dedicated IPv4 Address for Ingress](https://supabase.com/docs/guides/platform/ipv4-address)
- [PrivateLink](https://supabase.com/docs/guides/platform/privatelink)
- [Postgres SSL Enforcement](https://supabase.com/docs/guides/platform/ssl-enforcement)
