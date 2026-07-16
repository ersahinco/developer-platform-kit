# Hybrid Starter Reference

This reference composes explicit provider implementations without inventing a
cloud abstraction:

```text
Cloudflare DNS -> Hetzner Compose -> Supabase PostgreSQL -> AWS S3
                         |-> Dapr service invocation
                         `-> Dapr + Redis pub/sub
```

AWS/ECS remains the reviewed enterprise production default. The hybrid target
is a starter reference: a single VM, public TLS, scoped credentials, explicit
availability limits, and operator-owned recovery.

## Delivery product decision gate

[ADR 0003](adr/0003-retain-direct-hetzner-compose-reference.md) retains this
direct Terraform and Compose realization and freezes its operator surface.
Coolify, Portainer, Kamal, Dokku, Dokploy, and CapRover are not runtime
dependencies. Do not add a deployment UI, fleet manager, generic product
adapter, or second control plane to this reference.

Correctness, security, compatibility, tests, and evidence may improve. A new
rollout, scheduling, secret-management, fleet, or UI capability first requires
the bounded product-adoption experiment in ADR 0003. A successful product must
replace this operator implementation rather than create a parallel path.

Mutable concerns keep one owner:

| Concern | Source of truth |
|---|---|
| Infrastructure and DNS | Terraform in the isolated hybrid roots |
| Workload identity | `platform/workloads.json` |
| Image build and digest | GitHub Actions App Build workflow |
| Deployment and rollback | Explicit hybrid Make targets and operator script |
| Runtime configuration | Git-tracked Compose and Dapr files |
| Secret values | Approved external secret authority; shell and host `.env` values are copies |
| TLS | Caddy on the runtime VM |
| Evidence | Project verifier and `scripts/observability/release_event.py` |

## Lifecycle and ownership

| Lifecycle | Terraform root | Owner | State key |
|---|---|---|---|
| Foundation | existing `make bootstrap` | platform runtime | AWS state bucket and OIDC bootstrap |
| Data | `infra/hybrid-reference/data` | data platform | `<stack>/hybrid/data.tfstate` |
| Compute | `infra/hybrid-reference/compute` | platform runtime | `<stack>/hybrid/compute.tfstate` |
| DNS | `infra/hybrid-reference/dns` | platform runtime | `<stack>/hybrid/dns.tfstate` |

Only the bucket name, region, project reference, VM address, and DNS record
identity cross lifecycle boundaries. Database URLs and credentials are never
Terraform outputs. The Supabase database password is necessarily present in
the encrypted data-root state because the provider requires it at project
creation.

The capability inventory is
`infra/catalog/capability-realizations.yaml`. It is discovery metadata, not a
composer manifest. Provider options and lifecycle choreography remain visible
in the three roots and Make targets.

## Cost and availability

The main cost drivers are the Hetzner VM, Supabase plan and database size, S3
objects/requests/egress, and DNS zone already owned in Cloudflare. Review each
provider's calculator before apply; this repo does not freeze price estimates.

Starter limitations are deliberate:

- one VM and one local Redis process; VM maintenance or loss causes downtime
- Redis persistence stays on the VM root disk; replacement can lose unconsumed
  starter-lane messages
- public database connectivity unless the chosen Supabase plan and network
  path provide stronger controls
- scoped static S3 credentials owned and rotated by an operator
- S3-managed at-rest encryption; a customer-managed KMS key requires a named
  policy, rotation, cost, and recovery owner before production admission
- no Cloudflare proxy dependency; the unproxied origin owns ACME TLS
- Supabase plan limits and restore process define database availability and
  recovery objectives

The enterprise lane remains ECS, private AWS networking, task identity,
managed HA, CloudWatch evidence, and the SNS/SQS-backed Dapr component.

## Configure

Bootstrap the existing encrypted/versioned Terraform state bucket, then create
ignored local variable files:

```bash
make bootstrap
cp infra/hybrid-reference/data/stack.tfvars.example infra/hybrid-reference/data/stack.tfvars
cp infra/hybrid-reference/compute/stack.tfvars.example infra/hybrid-reference/compute/stack.tfvars
cp infra/hybrid-reference/dns/stack.tfvars.example infra/hybrid-reference/dns/stack.tfvars
```

Set provider credentials and the one sensitive Terraform input in the shell:

```bash
export AWS_PROFILE=...                    # or another short-lived AWS identity
export HCLOUD_TOKEN=...
export CLOUDFLARE_API_TOKEN=...
export SUPABASE_ACCESS_TOKEN=...
export TF_VAR_supabase_database_password=...
```

The data apply creates the declared Supabase project. To adopt an existing
project, make the project variables match it, initialize the data root, import
its project reference, and review the next plan before any apply:

```bash
make hybrid-reference-data-init
terraform -chdir=infra/hybrid-reference/data import \
  -var-file=stack.tfvars supabase_project.reference "$SUPABASE_PROJECT_REF"
make hybrid-reference-data-plan
```

The database password is used at creation but ignored after create or import;
rotation stays with the database owner instead of Terraform drift repair.

Create the starter S3 credential owner outside this reference and set its name
in `export_writer_user_name`. The data root grants that existing user only
`s3:PutObject` through an IAM group. It never creates an IAM user or access key,
so credential material cannot enter Terraform state. Create and rotate the
access key out of band, then export its values only in the deployment shell.

Build each image once and deploy its resolved digest. The existing **App Build**
workflow publishes the AWS-admitted workloads and Liquibase and now prints
immutable `repository@sha256:...` references. Use the API digest from that run
unchanged in ECS or Hetzner. `booking_api` is reference-only today, so publish
it with the standard shared Dockerfile to the registry you operate:

```bash
docker buildx build --push -f platform/workload.Dockerfile \
  --build-arg APP_PATH=apps/booking_api \
  --build-arg UV_PACKAGE=aws-sdlc-containers-booking-api \
  --build-arg 'WORKLOAD_CMD=python -m booking_api.main' \
  -t "$HYBRID_REGISTRY/booking-api:$IMAGE_TAG" .
docker buildx imagetools inspect "$HYBRID_REGISTRY/booking-api:$IMAGE_TAG"
```

Then export digest references for every runtime image:

```bash
export API_IMAGE=registry.example/api@sha256:...
export BOOKING_API_IMAGE=registry.example/booking-api@sha256:...
export EVENT_CONSUMER_IMAGE=registry.example/event-consumer@sha256:...
export DATA_EXPORT_IMAGE=registry.example/data-export-job@sha256:...
export LIQUIBASE_IMAGE=registry.example/liquibase@sha256:...
```

For a private registry, set `REGISTRY_HOST`, `REGISTRY_USERNAME`, and
`REGISTRY_PASSWORD`. The password is sent through SSH standard input and is not
placed in Terraform, cloud-init, or a command argument. Registry login uses a
temporary Docker config that is removed after the images are pulled.

Set runtime secrets and boundaries. Request workloads receive the Supabase
transaction-pool URL as `DATABASE_URL`; consumers and jobs receive the direct
URL under the same app-facing name. Liquibase uses its own direct JDBC URL.
TLS verification must remain enabled.

```bash
export HYBRID_HOSTNAME=api.example.com
export ACME_EMAIL=platform@example.com
export POOLED_DATABASE_URL='postgresql://...?...sslmode=verify-full'
export DIRECT_DATABASE_URL='postgresql://...?...sslmode=verify-full'
export LIQUIBASE_DATABASE_URL='jdbc:postgresql://...?...sslmode=verify-full'
export LIQUIBASE_DATABASE_USERNAME=...
export LIQUIBASE_DATABASE_PASSWORD=...
export PRIMARY_EDGE_AUTH_TOKEN=...
export DATA_EXPORT_AWS_ACCESS_KEY_ID=...
export DATA_EXPORT_AWS_SECRET_ACCESS_KEY=...
export DATA_EXPORT_AWS_SESSION_TOKEN=     # optional for temporary credentials
```

The `DATA_EXPORT_` prefix prevents scoped workload credentials from replacing
the AWS identity Terraform uses for state and IAM operations.

## Plan, deploy, and prove

`make hybrid-reference-plan` initializes each backend and produces a
non-mutating plan. The DNS plan uses the documentation-only address
`192.0.2.1` until compute exists; set `HYBRID_ORIGIN_IPV4` to preview another
address.

The full apply path enforces the safe order: data, compute, digest-pinned
deployment, Liquibase, private origin proof, DNS switch, public TLS proof, S3
export, and release evidence.

```bash
make hybrid-reference-prerequisites
make hybrid-reference-plan
make hybrid-reference-apply
```

Origin proof runs before DNS and verifies health, readiness, Prometheus
metrics, structured logs, Dapr service invocation, Redis-backed Dapr pub/sub,
and duplicate-event handling. Public proof then verifies DNS, ACME TLS, health,
readiness, and metrics. Export proof succeeds only after S3 accepts both the
data object and integrity manifest.

Evidence is written to `/tmp/aws-sdlc-containers-hybrid-evidence` by default.
It uses the existing release-event shape and correlates workload ID, API image
digest, runtime target, five capability realization IDs, operator workflow,
deployment address, and rollback category. Set `HYBRID_RUN_ID` to a CI or
operator-run identifier when one exists; otherwise the command creates a
timestamped local run identifier.

## Failure and recovery drills

| Failure | Command or recovery |
|---|---|
| Database unavailable | `make hybrid-reference-drill-database-unavailable` proves the adapter fails without changing the live service |
| Invalid S3 credentials / failed export | `make hybrid-reference-drill-invalid-s3` requires a non-zero job result |
| Duplicate event | included in `make hybrid-reference-verify-origin`; the receipt must record the duplicate |
| App image regression | set all `PREVIOUS_*_IMAGE` digest references, then run `make hybrid-reference-rollback` |
| VM loss | `make hybrid-reference-vm-replacement-plan`; review, then `make hybrid-reference-vm-replacement CONFIRM_VM_REPLACEMENT=replace-vm` |
| DNS rollback | set `PREVIOUS_ORIGIN_IPV4`, run the rollback plan, then `make hybrid-reference-dns-rollback-apply CONFIRM_DNS_ROLLBACK=rollback-dns` |
| Database recovery | Supabase owner restores or forward-fixes; app rollback never pretends to undo schema/data state |

## Destroy

Destroy is bounded to the three isolated states and runs DNS, compute, then
data. The S3 bucket defaults to `force_destroy = false`, so retained evidence
prevents accidental deletion.

```bash
make hybrid-reference-destroy CONFIRM_HYBRID_DESTROY=destroy-hybrid
```

## Terraform/OpenTofu compatibility

Terraform is canonical. `make infra-compatibility` runs mocked non-production
plans with Terraform and OpenTofu and compares planned resource addresses and
actions. Shared roots use compatible HCL and do not use OpenTofu-only state
encryption or language features. If behavior differs, the Terraform result is
authoritative.

Provider references: [Hetzner Cloud](https://github.com/hetznercloud/terraform-provider-hcloud),
[Cloudflare](https://developers.cloudflare.com/api/terraform/),
[Supabase](https://supabase.com/docs/guides/deployment/terraform), and
[OpenTofu compatibility](https://opentofu.org/docs/intro/migration/).
