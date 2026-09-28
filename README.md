# Developer platform kit

Start app, infrastructure, and data repositories from three maintained templates.
Teams own the generated code and reuse GitHub Actions workflows and AWS Terraform
modules. Developers use a Python CLI or Backstage; both produce the same files.

Platform engineers maintain the starters and delivery rules once. Developers get
working examples, tests, ownership metadata, and a clear path to delivery without
assembling each repository from scratch. Generated applications have no runtime
dependency on this kit.

Delivery targets are AWS ECS/Fargate and EMR Serverless. The optional CNOE lab
exercises portal integration locally. Shared hosting runs on an on-premises Docker host or AWS ECS/Fargate, using the
client's existing services. Hosting on-premises does not change the starters' AWS
delivery targets or provide an air-gapped platform. Client sign-in and AWS delivery
require acceptance testing in that environment.

[CLI](#start-a-repository) · [Backstage](#backstage-self-service) ·
[Shared hosting](#host-a-shared-portal) · [Local lab](#local-cnoe-lab) ·
[Contributing](#contribute)

| Use | Maintainer entry point | Developer entry point |
|---|---|---|
| CLI only | `make cli-build` produces a wheel for your artifact store | Install the wheel; run `dpk` from any directory |
| Local portal | `make portal-up`, then `make portal-credentials` | Open the local Backstage URL |
| Shared portal | Build the image, then use the [on-premises or AWS hosting example](#host-a-shared-portal) | Open the team's portal URL and sign in with Entra |

## Start a repository

Clone this repository and run from its root with Python 3.13+. Rendering uses
only the standard library; no package installation or local platform is needed.

```bash
python3 -m scaffold.new_repo list
python3 -m scaffold.new_repo describe app
python3 -m scaffold.new_repo render app ../orders-api \
  --set WORKLOAD_NAME=orders-api \
  --set OWNER=team-payments \
  --set REPOSITORY=acme/orders-api \
  --set AWS_REGION=eu-central-1 \
  --set TOOLKIT_REPOSITORY=ersahinco/developer-platform-kit \
  --set TOOLKIT_REF=81009fac4cb1a77a1800efdf249af3bab3d1aae3
```

`describe` lists required variables and examples. Rendering validates them before
writing. Pin a published full commit SHA or immutable release tag; floating
branches are rejected. Review the generated README, then publish with Git/GitHub.
The CLI creates files; repository creation and catalog registration are separate.

To install the commands from a checkout, run `make cli-install` (requires
[uv](https://docs.astral.sh/uv/guides/tools/)). Then use `dpk list`, `dpk describe app`,
and `dpk render` with the same arguments above, from any directory.
`dpk-backstage` exports portal templates. Run `uv tool update-shell` if the commands
are not on your PATH. Re-run `make cli-install` after updating the checkout.

For enterprise distribution, promote an approved CI build to the client's artifact
store. The **Scaffold & Python** job saves `cli-COMMIT_SHA` for 14 days; choose a
successful **whole CI run** for the intended commit. From the Actions page download
the artifact, or use:

```bash
gh run download RUN_ID --repo ersahinco/developer-platform-kit \
  --name cli-COMMIT_SHA --dir /tmp/dpk-cli
cd /tmp/dpk-cli
shasum -a 256 -c SHA256SUMS
uv tool install ./developer_platform_kit-0.1.0-py3-none-any.whl
dpk list
```

Substitute the approved run ID and full commit SHA. `make cli-build` produces the
same wheel and source archive locally in `dist/`. For a Python package feed,
maintainers upload the wheel using the client's publishing process. Developers
configure that feed's authentication, then install a pinned version:

```bash
uv tool install --default-index https://packages.example.com/pypi/simple \
  developer-platform-kit==0.1.0
```

Use the client's credential helper; keep tokens out of commands, URLs, and Git.
The CLI has no runtime dependencies beyond Python 3.13+ and bundles all starters.
No portal, checkout, or cloud credentials are needed to render. Use
`uv tool install --reinstall ...` to replace an installed version. CI artifacts are
commit snapshots, not releases: increment `project.version` before promoting a
changed wheel, retain old versions, and never overwrite a published version.
No public package registry publication is configured.

| Starter | Includes | Delivery modes |
|---|---|---|
| `app` | Container host, health/readiness, metrics, JSON logs, tests, dependency lock | `build`: test, build, scan, optionally publish. `deploy`: release an existing image by digest |
| `infra` | Terraform root, state configuration, module composition, catalog metadata | `plan`: validate, lint, scan, save plan. `apply`: apply the reviewed plan |
| `data` | Spark ETL/ELT, JSON quality checks, Liquibase migrations, tests, dependency lock | `migrate`: run a published migration image. `pipeline`: package and execute Spark |

Build never deploys; plan never applies. App and migration-image builds run
without cloud credentials until `PUBLISH_IMAGES=true` enables ECR publication.
Configure AWS OIDC and an existing ECR repository before enabling it. Published
tags identify commits, and releases resolve images to digests.

Infra apply checks the source workflow, successful default-branch plan, current
head, state location, Terraform version, and provider lock. Cloud-changing modes
write `release-event.json`; apply and data execution require confirmation strings.

## Backstage self-service

Export the same starters for an existing Backstage portal:

```bash
python3 -m scaffold.backstage /tmp/toolkit-backstage \
  --allowed-owner your-github-org \
  --set OWNER=team-payments \
  --set AWS_REGION=eu-central-1 \
  --set TOOLKIT_REPOSITORY=ersahinco/developer-platform-kit \
  --set TOOLKIT_REF=81009fac4cb1a77a1800efdf249af3bab3d1aae3
```

The installed `dpk-backstage` command takes the same arguments. Publish the
exported directory to a template repository and register its
`catalog-info.yaml`. Install Backstage's native GitHub scaffolder module and
configure its GitHub integration. The basic flow uses `fetch:template`,
`publish:github`, and `catalog:register`; see
[Software Templates](https://backstage.io/docs/features/software-templates/writing-templates/).

`--set` fixes platform-owned values and removes them from the developer form;
task parameters cannot override them. For example, add
`--set STATE_BUCKET=your-existing-state-bucket` for infra. Without fixed values,
the exporter keeps the full forms. Developers enter project details, create a
repository, and find it in the catalog.

Repeat `--allowed-owner` for multiple destinations. Omitting it permits any owner
on the selected host. Task schemas enforce host and owner even through direct API
requests; SCM credentials and portal permissions must also restrict access.
For GitHub Enterprise Server, add `--base-url https://github.example.com` and
configure the portal integration for that same host. The shipped delivery lanes
use GitHub.com hosted runners and artifact actions; adapt and verify their GHES
compatibility before promising delivery there. For Gitea, use `--provider gitea --base-url https://your-host/gitea` with the native
`publish:gitea` action. GitLab publishing and delivery are not implemented.

### Repository access and delivery settings

Pass `--github-settings /path/to/client-github.json` with exactly one allowed owner
to configure existing teams and delivery targets before the first commit starts CI.
Settings use native GitHub action fields, keyed by starter:

```json
{
  "app": {
    "collaborators": [{"team": "payments", "access": "push"}],
    "repoVariables": {"PUBLISH_IMAGES": "false", "ECS_CLUSTER": "existing-cluster"},
    "secrets": {"AWS_ROLE_ARN": "arn:aws:iam::123456789012:role/app-delivery"}
  }
}
```

Replace these identifiers with the client's existing resources. Variables must be
consumed by that starter's workflow. The `secrets` field accepts only IAM role
ARNs, which are identifiers; access keys and publishing tokens must never enter
exported files. SCM credentials stay in Backstage's integration configuration.
See [the complete settings example](tests/fixtures/github-settings.json).
Omitting a starter preserves its basic publish/register flow.

Configured starters use native `github:repo:create`, `github:environment:create`,
and `github:repo:push`. The `aws` environment permits only `main`; infra also gets
`aws-plan` for pull-request planning with a separate `AWS_PLAN_ROLE_ARN`.
The apply role trusts `aws`, the limited planning role trusts `aws-plan`, and
image publication roles trust the repository's `refs/heads/main` subject.
The planning role must not be able to apply changes.

These steps create no AWS resources. ECR repositories, services, state, and roles
must exist before delivery runs. Grant the GitHub App the native action
[permissions](https://backstage.io/docs/integrations/github/github-apps/#app-permissions),
then configure required reviewers and approval rules in GitHub. Native collaborator
assignment can warn without failing the task: verify team access during acceptance.
A failed setup can leave an empty repository; inspect its task log before retrying.

Employee AWS access through Entra federation, GitHub Actions OIDC delivery roles,
and workload runtime roles serve different purposes. Reuse the client's existing
accounts and roles; employee access alone does not configure CI access.

## Host a shared portal

Use an existing Backstage installation, or build the shared portal image:

```bash
make portal-image IMAGE=registry.example.com/platform/backstage:0.1.0
```

This builds locally without starting Kind or configuring the local lab. Build for
the target runtime's CPU architecture; prefix the command with
`DOCKER_DEFAULT_PLATFORM=linux/amd64` for the AWS example's default X86_64 tasks.
After resolving the upstream licensing
boundary below, publish to the client's registry and deploy by digest through its
existing delivery process. Export and publish templates with `dpk-backstage`,
using fixed client defaults and `--github-settings` as described above.

The image listens on port 7007 and starts
with `node packages/backend --config platform/entra.yaml`. The image includes
native [Microsoft sign-in](https://backstage.io/docs/auth/microsoft/provider/),
[Graph directory sync](https://backstage.io/docs/integrations/azure/org/), and
[GitHub App integration](https://backstage.io/docs/integrations/github/github-apps/).
Direct Entra sign-in needs no Keycloak deployment.

The examples below reuse PostgreSQL, TLS termination, and secret injection.
The client owns backups and monitoring. Use the native
`/.backstage/health/v1/readiness` check through the existing runtime. On Kubernetes,
set `automountServiceAccountToken: false`: scaffolding needs no cluster credentials,
and the upstream app otherwise enables optional Kubernetes plugins when it finds
the token. Resolve the upstream image licensing boundary described below before
redistributing an image.

Supply these values through the runtime and secret store; configuration lives in
[platform/backstage/entra.yaml](platform/backstage/entra.yaml):

| Values | Purpose |
|---|---|
| `PORTAL_URL` | External HTTPS URL |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DATABASE`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Existing database; the user needs schema creation inside it, not database creation |
| `SESSION_SECRET` | Persistent random key shared across portal replicas |
| `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET` | Tenant-specific Web application registration |
| `ENTRA_CREATORS_GROUP_ID`, `ENTRA_VIEWERS_GROUP_ID` | Directory groups to import with their direct user members |
| `ENTRA_CREATORS_GROUP_REF`, `ENTRA_VIEWERS_GROUP_REF` | Imported group refs, e.g. `group:default/platform-creators`; native Graph uses normalized names, not IDs |
| `GITHUB_APP_ID`, `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_ORGANIZATION` | Scoped GitHub App; this integration requires client credentials as well as the signing key |
| `TEMPLATES_CATALOG_URL` | Published `catalog-info.yaml` from the export; readable by the GitHub App |
| `GITHUB_HOST`, `GITHUB_API_URL` (optional) | Set both for GHES, e.g. `github.example.com` and `https://github.example.com/api/v3`; defaults are GitHub.com |

Register `PORTAL_URL/api/auth/microsoft/handler/frame` as the Entra Web redirect.
Grant the native provider's delegated sign-in permissions and Graph application
permissions `User.Read.All` and `GroupMember.Read.All`, with tenant consent.
Directory sync runs every 15 minutes. Confirm group refs against their
`graph.microsoft.com/group-id` annotations and update refs after group renames.
Set exported `OWNER` to the owning group's catalog name.

The native resolver requires a catalog user matched by `graph.microsoft.com/user-id`,
with no email or missing-user fallback. Only configured template locations may
supply executable templates; developers can register their generated components.
Keep PostgreSQL certificate validation enabled. For a private database issuer,
inject its PEM bundle through native `APP_CONFIG_backend_database_connection_ssl_ca`.
For other private HTTPS issuers, mount the client's CA and set `NODE_EXTRA_CA_CERTS`.
Allow network access to Entra, Microsoft Graph, GitHub/API, the template host,
registry, and PostgreSQL. An internal URL alone does not make the portal offline.

### On-premises Docker host

Use Docker Compose 2.24.4+ on a Linux host with an existing HTTPS reverse proxy and
PostgreSQL. The [Compose file](platform/hosting/compose.yaml) runs only Backstage;
port 7007 binds to loopback for the host proxy, not the network. The image runs as
an unprivileged user with capabilities dropped. Start with:

```bash
mkdir -p platform/.local
cp platform/hosting/portal.env.example platform/.local/portal.env
chmod 600 platform/.local/portal.env
# Fill in client values and the published image digest; single-quote secrets.
make portal-host-up
make portal-host-status
```

Point the host proxy at `http://127.0.0.1:7007`, preserve the public host and HTTPS
forwarded headers, and set `PORTAL_URL` to that public HTTPS URL. The example env
file is a single-host handoff; have the client's secret store supply it with
restricted permissions. A single-quoted PEM key can contain real line breaks.
`portal-host-up` validates Compose, requires an image digest, and waits for health.
For failures, inspect `docker compose --env-file platform/.local/portal.env -f
platform/hosting/compose.yaml logs --tail 100 backstage` in your terminal. Re-run
`portal-host-up` after configuration or image changes. `portal-host-down` stops the
portal; the external database remains. This profile is a single-host deployment.

### AWS ECS/Fargate

The [CloudFormation example](platform/hosting/aws.yaml) creates a portal task,
service, and 30-day log group. It expects an existing ECS cluster, private subnets,
security groups, ECR image, database, and ALB target group attached to an HTTPS
listener. Use an **IP** target group on port **7007**, with health path
`/.backstage/health/v1/readiness`. Permit ingress to the tasks only from the ALB.

Store the required values from `portal.env.example` as a JSON object in Secrets
Manager (exclude `PORTAL_IMAGE`). Pass its full ARN as `ConfigurationSecret`.
ECS injects the named keys; no secret values enter CloudFormation parameters.
For a private database CA, supply `DatabaseCASecret` as a separate plain PEM
secret. Optional GitHub host/API values are stack parameters. The existing task
execution role needs ECR pull, log write, and access to those secrets and their
KMS keys. The portal receives **no AWS task role**.

Create a reviewed change set through the client's infrastructure pipeline using
`platform/hosting/aws.yaml`. Its parameters describe each existing-resource input;
`Image` requires a digest and `Architecture` must match the build. It defaults to
one 1-vCPU/2-GB task; set `Replicas=2` across multiple subnets for host redundancy.
Private subnets need outbound access to the integrations above, including registry,
logs, and secret endpoints. Fargate gives tasks no public IP.

The service uses readiness checks and deployment rollback. Rotate secret values
through the secret store, then replace tasks: running tasks do not automatically
receive new values. Keep the session key stable across replicas and routine
rollouts. Roll back by deploying a previous image digest; review database migration
compatibility first. The stack retains its log group when removed.

### Client acceptance

Before handing out the URL, verify a creator can scaffold and register a private
repository, a viewer cannot create or write, and an unrelated user cannot sign in.
Check imported group refs, template visibility, team access, and the generated
repository's CI. Then run a reviewed AWS deployment using the client's OIDC roles.
Exercise a restart and database restore, and connect failed tasks, readiness, and
logs to the client's monitoring. These require live client access; local checks do
not certify the client's identity, network, availability, or recovery setup.

## Local CNOE lab

The optional lab assembles pinned [CNOE packages](https://cnoe.io/docs/reference-implementation/local)
for Kind, Gitea, Argo CD, Backstage, Keycloak, and External Secrets. Shared-portal
users need none of this on their laptops. The lab creates no cloud resources.

Install Docker, Python 3.13+, kubectl, Kind, and idpbuilder (verified with 0.10.2):

```bash
make portal-up              # Start or update the lab
make portal-status          # Argo conditions and Backstage pods
make portal-credentials     # Print local login passwords in your terminal
make portal-verify          # Check identity, permissions, TLS, destinations
make portal-smoke           # Create all three starters in local Gitea
make portal-down            # Delete this lab and its local repositories
```

The first source build takes several minutes; later builds reuse Docker's cache.
The lab was tested with 12 GB allocated to Docker and builds for the host's
architecture, including ARM. State, credentials, and kubeconfig stay ignored in
`platform/.local/`; your default kubeconfig is unchanged. Template changes can
take about a minute to appear through native catalog processing.

Open [Backstage](https://cnoe.localtest.me:8443), sign in as `user1` with the
`USER_PASSWORD` from `portal-credentials`, and choose **Create**. Use a unique
repository name under the default `platform` Gitea owner. The
[Keycloak admin console](https://cnoe.localtest.me:8443/keycloak/admin/) uses
`cnoe-admin`, `KEYCLOAK_ADMIN_PASSWORD`, and the `cnoe` realm.

| User | Group | Access |
|---|---|---|
| `user1` | `scaffold-creators` | Browse, scaffold, read/cancel tasks, register components |
| `user2` | `scaffold-viewers` | Browse catalog and template listings; creation forms and writes denied |

Both demo users share `USER_PASSWORD`; `portal-up` manages their groups. Sign in
again after membership changes because issued tokens retain claims until expiry.
The backend denies unknown permissions and groups. Creators are trusted catalog
contributors with access to the configured native scaffolder actions.

`portal-verify` checks real sign-ins, denied writes, group removal/restoration,
destination validation, TLS, and restricted cluster access. `portal-smoke`
compares every generated file with CLI output; it refuses the GitHub profile.
Gitea uses server-default visibility and does not run GitHub Actions workflows.
GitHub publishing creates private repositories.

`portal-up` exports the public CA to `platform/.local/platform-ca.crt`. Import it
into your workstation trust store to trust the browser endpoint; replace it after
rebuilding the cluster. Keep CA private keys, SCM tokens, and credential output
local. External Secrets generates the persistent session key. Shared hosting
must use its own identities, credentials, maintained images, and backups.

If bootstrap times out, inspect `portal-status`. A ready pod does not prove Argo
can fetch templates: a DNS `ComparisonError` blocks reconciliation. Resolve its
reported cause, then run `python3 platform/bootstrap.py` to retry without rebuilding.

<details>
<summary>Optional personal GitHub integration</summary>

Sign-in and publishing are separate. To add GitHub sign-in:

1. Register a [GitHub OAuth App](https://github.com/settings/applications/new)
   with homepage `https://cnoe.localtest.me:8443` and callback
   `https://cnoe.localtest.me:8443/keycloak/realms/cnoe/broker/platform-github/endpoint`.
2. Run `make portal-identity PROVIDER=github` and enter the client credentials at
   the prompts. Native `google` and `microsoft` providers are also supported;
   personal Microsoft accounts need an app registration that permits them.
3. Choose the provider in Keycloak, then authenticate as an existing local user
   to link accounts. Email matching never links accounts automatically. Verify in
   the browser; the lab identifies users by immutable OIDC `sub`.

For publishing, run `make portal-github OWNER=your-owner`, then `make portal-up`
and `make portal-verify`. The hidden prompt takes a dedicated, expiring token;
it never reuses `gh` credentials. A fine-grained token needs **Administration**,
**Contents**, and **Workflows** write access and **All repositories** for the
selected owner, because a new repository cannot be preselected. A classic token
with `repo` and `workflow` is an alternative, subject to organization policy.
See [GitHub token permissions](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

Native integration config is saved with mode `0600` in ignored
`platform/.local/backstage-integrations.json` and mounted as a Kubernetes Secret;
`platform/.local/github-owner` selects the destination. Optional native repository
settings go in `platform/.local/github-settings.json`. Run `portal-up` after edits.
For an organization, use a scoped GitHub App in the native integration config.

Create an app to verify publishing and catalog registration. Leave `PUBLISH_IMAGES`
unset during a demo. A private toolkit repository must permit destination repos
under **Settings → Actions → General → Access** for
[reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/share-across-private-repositories).
Publishing, catalog reading, workflow access, and AWS delivery are separate grants.
To return to Gitea, remove the local GitHub owner, integration, and optional settings
files, run `portal-up`, and revoke the unused token.

</details>

## Maintain the kit

```text
repo-templates/{app,infra,data}/    manifests and repository skeletons
.github/workflows/reusable-*.yml   one delivery lane per audience
modules/aws/                      Terraform capabilities used by infra
scaffold/                         stdlib CLI and Backstage export
platform/                         upstream CNOE assembly and native integrations
tests/                            rendering and delivery contracts
```

### Upstream ownership

`platform/prepare.py` clones a pinned `cnoe-io/stacks` revision into ignored
`platform/.local/stacks/` and stages selected packages in `.local/packages/`,
retaining upstream licenses. These are disposable build outputs. idpbuilder
publishes them into local Gitea; Argo CD reconciles them. Maintain overlays and
explicit patches here, not a second copy of upstream source.

| Local code | Reason it exists |
|---|---|
| `prepare.py`, `applications/`, `config/` | Export this kit's templates and assemble validated CNOE/Kustomize configuration |
| `identity.py` | Maintain local scopes, demo groups, and authenticated account linking through Keycloak's Admin API; realm import skips an existing realm |
| `bootstrap.py` | Create the Gitea destination and wait for Argo to observe the published revision |
| `runtime.py` | Supply CA trust and native SCM credentials through Kubernetes resources |
| `config/session-secret.yaml` | Configure External Secrets' native password generator |
| `backstage/`, `image.py` | Build pinned CNOE source with native providers and group-based authorization |
| `hosting/` | Native Compose and CloudFormation examples connecting that image to existing client services |

The Backstage Dockerfile pins its source archive and Node image by digest and
applies `backstage/source.patch` with the upstream lockfile. The patch registers
native Microsoft/Graph modules and our permission policy, selects the sign-in
provider, and fixes the local Keycloak subject. No compiled bundle is rewritten.
The unused Terraform viewer is disabled because it exposes server file reads.
The pinned scaffolder 3.4.0 ignores plain `DENY` on task lists; the policy uses
its native empty task-owner condition for non-creators. Live checks cover this.
`keycloak/setup.patch` fixes the local bootstrap's ARM support, resumability, and
secret-safe logging. Remove these workarounds when adopted upstream revisions
supply the fixes.

Review against the pinned
[CNOE packages](https://github.com/cnoe-io/stacks/tree/32160ecb5942b6d0199b1cef039cc3457d2b1100/ref-implementation),
[Backstage source](https://github.com/cnoe-io/backstage-app/tree/6a5087c2fb6aeccdee5f2b5665f7d93cb89640b3),
and [Keycloak import behavior](https://www.keycloak.org/server/importExport).
The pinned CNOE Backstage app has no top-level license file: clarify redistribution
terms with upstream before distributing a client image. Dependency licenses and
the upstream README remain in the image.

### Infrastructure boundaries

The infra starter calls all ten AWS modules: `network`, `ecr`, `github-oidc`,
`ecs-cluster`, `alb`, `ecs-service`, `ecs-job`, `postgres`, `object-storage`, and
`emr-serverless`. Remove unused capabilities before applying billable resources.
Follow its README for state and identity setup. Keep plan/apply roles separate,
plan artifacts private and short lived, and database credentials in Secrets Manager.

The starter supports one public service and ALB target group. Terraform owns
service shape; delivery owns task revisions. Images must match the X86_64 task
default. Spark requires fresh output paths; use run-specific prefixes and design
promotion in the consuming repo. Azure/GCP delivery is not implemented.

## Contribute

Open an issue for a bug or proposed change; include a reproduction and expected
behavior. Submit a small pull request explaining the problem, the change, and the
checks run. Discuss a new audience or runtime target before adding one.

Use `.devcontainer/` for the check tools, or install them locally and run:

```bash
uv sync --frozen
make test                   # Fast gate: render all starters and check contracts
make check                  # Python, workflows, Terraform, TFLint, Checkov, Dockerfiles
make secret-scan
```

CI also installs the built CLI away from the checkout and compares every rendered
file and Backstage export with the source version (`make cli-check`). It tests
generated Python repositories with their locks and builds/tests the Backstage
image. `make hosting-check` validates Compose and CloudFormation without deploying.
For platform changes, run `make portal-check`; it also boots the actual Compose
service against disposable PostgreSQL with verified TLS and a non-superuser,
without external identity calls. Changes affecting
sign-in or publishing also need `portal-up`, `portal-verify`, and `portal-smoke`
with the local Gitea profile. Update upstream pins and patches together.

Keep three templates and three lanes. Prefer native integration and declarative
configuration; custom code needs a verified gap and a current consumer. Modules
need callers in a template. Add tests for behavior changes, keep user documentation
in this README and generated READMEs, and follow [AGENTS.md](AGENTS.md) for editing
rules. Never commit `platform/.local/`, generated packages, or credentials.

## License

Original code is licensed under [MIT](LICENSE). Generated starters retain that
license in `NOTICE`; teams choose the terms for their own additions. Upstream
dependencies retain their own terms, including the CNOE image redistribution
limitation described above.
