# Developer platform kit

Tested app, infrastructure, and data starters for teams using **GitHub and AWS**.
Application and data developers get code they can own, tests, dependency locks,
and delivery workflows. Platform contributors maintain those shared starting
points so each team has less setup to repeat. Generate the same repositories
through the Python CLI or Backstage; generated applications have no runtime
dependency on this kit.

The optional portal builds on [CNOE](https://cnoe.io/): its pinned Backstage app,
idpbuilder, and existing native integrations. This kit adds three templates,
three GitHub Actions delivery lanes, AWS Terraform modules, and explicit overlays.
Use the CLI on its own or export templates into an existing Backstage installation.

The supported delivery path is GitHub.com Actions to AWS ECS/Fargate and EMR
Serverless. The app can be generated and tested, including CI, without AWS
credentials. Portal hosting is separate: an optional local CNOE lab, an
on-premises Docker host, or AWS ECS/Fargate. Gitea supports local scaffolding;
GHES delivery needs separate verification. Azure, GCP, and GitLab delivery are
not implemented.

[CLI](#start-a-repository) · [Backstage](#backstage-self-service) ·
[Shared hosting](#host-a-shared-portal) · [Local lab](#local-cnoe-lab) ·
[Contributing](#contribute) · [MIT license](LICENSE)

| Use | Maintainer entry point | Developer entry point |
|---|---|---|
| CLI only | `make cli-build` produces a wheel for your artifact store | Install the wheel; run `dpk` from any directory |
| Local portal | `make portal-up`, then `make portal-credentials` | Open the local Backstage URL |
| Shared portal | Build the image, then use the [on-premises or AWS hosting example](#host-a-shared-portal) | Open the team's portal URL and sign in with Entra |

## Start a repository

### Generate and test an app

You need Git, Python 3.13+, and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Rendering itself uses only Python's standard library. The app tests need network
access to download locked dependencies, but no Docker, portal, or AWS account.

**Access today:** this repository is private and no public package release is
published. The commands below require repository access or an approved mirror.
Public visibility and release publication are separate maintainer decisions.

Clone the kit, then choose the GitHub owner for your eventual app repository:

```bash
git clone https://github.com/ersahinco/developer-platform-kit.git
cd developer-platform-kit
GITHUB_OWNER=your-github-user
python3 -m scaffold.new_repo list
python3 -m scaffold.new_repo describe app
python3 -m scaffold.new_repo render app ../orders-api \
  --set WORKLOAD_NAME=orders-api \
  --set OWNER=team-payments \
  --set REPOSITORY="$GITHUB_OWNER/orders-api" \
  --set AWS_REGION=eu-central-1 \
  --set TOOLKIT_REPOSITORY=ersahinco/developer-platform-kit \
  --set TOOLKIT_REF=2e8ba04fd61e06ff92afae938156690aaa6ec5a9

cd ../orders-api
uv sync --locked
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked pytest -v
```

Expect **5 passed** from the app tests. `uv` installs the Python version from
`.python-version`; `--locked` refuses to change `uv.lock`. `OWNER` is catalog
metadata and `AWS_REGION` is future deployment configuration; neither needs a
live service. To run the app, follow its generated README.

`describe` lists required variables and examples. Rendering validates them before
writing and refuses a nonempty destination. The CLI creates files; GitHub
repository creation and catalog registration are separate.

### Get green GitHub CI

Before pushing, ensure the destination can call the pinned reusable workflow.
For this private toolkit, **Settings → Actions → General → Access** must allow
eligible private caller repositories under the same owner. A developer's clone
access does not grant a workflow access. For another owner, use an approved
toolkit mirror owned there and set `TOOLKIT_REPOSITORY` and `TOOLKIT_REF` when
rendering. See [GitHub's private workflow sharing rules](https://docs.github.com/en/actions/how-tos/reuse-automations/share-across-private-repositories).

In the generated app directory, with [GitHub CLI](https://cli.github.com/)
authenticated and an unused repository name:

```bash
git init -b main
git add .
git commit -m "Start orders API"
gh repo create "$GITHUB_OWNER/orders-api" --private --source=. --remote=origin --push
gh run list --workflow delivery.yml
# Copy the run ID from the list:
gh run watch RUN_ID --exit-status
```

Leave `PUBLISH_IMAGES` unset and add no AWS secrets. **Delivery** should pass
**Test** and **Build / Build & Scan**, with deployment skipped. GitHub Actions
must be enabled, allow the pinned actions, and have hosted-runner capacity.
If GitHub rejects the workflow reference, no jobs started: correct access or
the pin. If a job starts and fails, inspect that job's log for the failing test,
build, or vulnerability scan. A queued run needs runner capacity, not AWS keys.

Verified on 2026-09-29: an app generated outside the checkout by the installed
wheel passed its five local tests and the complete
[GitHub Delivery run](https://github.com/ersahinco/dpk-beginner-check-20260929/actions/runs/36580863177).
That private verification repository has no repository secrets or variables;
AWS authentication, image publication, and deployment were skipped.

### Deployment comes later

For app delivery, provision ECR and the ECS cluster/service/task family, configure
an OIDC role and protected `aws` environment, then set `AWS_ROLE_ARN`, `ECS_CLUSTER`,
and `PUBLISH_IMAGES=true` as described in the generated README. The existing
service must have the workload name and an `app` container. Publishing writes to
ECR on main pushes; manual deployment releases an existing image by digest.
Infra and data execution need their own state, roles, and services. Their generated
READMEs describe those prerequisites; a green app build does not verify deployment.

### Install or distribute the CLI

From the **kit checkout**, run `make cli-install` (requires
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
The wheel bundles all starters. Use `uv tool install --reinstall ...` to replace
an installed version. Before promoting a CI snapshot, increment `project.version`;
retain previous releases and never overwrite published versions. Public package
registry publication is not configured.

### What is pinned

The manifest examples, README commands, and local portal defaults use toolkit
commit `2e8ba04fd61e06ff92afae938156690aaa6ec5a9`, which passed the
[whole kit CI run](https://github.com/ersahinco/developer-platform-kit/actions/runs/36545905406).
Use one tested toolkit revision for workflows and modules together. The renderer
rejects branch names but does not query GitHub or prove a tag is immutable; a full
commit SHA is preferred. Example version strings are not a promise of a release.

`make cli-check` installs both the wheel and a wheel rebuilt from the source
archive outside the checkout, then compares all three starters and Backstage
exports byte for byte with the source. The wheel contains the renderer, templates,
and MIT notice; it does not bundle delivery workflows, Terraform modules, or CNOE.
Those remote references still require repository access.

App/data dependencies are locked in `uv.lock`; CI uses uv 0.11.8. Terraform
modules are pinned by toolkit ref, but the first `terraform init` selects an AWS
provider within `~> 6.0`: commit the generated `.terraform.lock.hcl` to preserve
that selection. The kit's infra tests use local modules; they do not prove remote
access. A consumer can check the real module URLs with `terraform init
-backend=false` and `terraform validate`, without AWS credentials. Private module
downloads need Git authentication on the machine or runner independently of
reusable-workflow access; no cross-repository Git credential setup is bundled.
Use an approved accessible mirror when necessary.

These pins reproduce starter content and dependency selections, not bit-for-bit
images forever: Python image tags, hosted runners, provider selection before the
first lock, and vulnerability databases can change. Review updates in the
consuming repository and retain its locks and reviewed image digests.

The remote infra module URLs above were fetched and validated on 2026-09-29
using Terraform 1.15.8 and AWS provider 6.66.0 with the S3 backend disabled.
This checks remote access and module compatibility; it does not exercise AWS.

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
  --set TOOLKIT_REF=2e8ba04fd61e06ff92afae938156690aaa6ec5a9
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
Resolve the [upstream licensing boundary](#upstream-ownership), then publish to the
client's registry and deploy by digest. Export templates with `dpk-backstage`, using
fixed client defaults and `--github-settings` as described above.

The image listens on port 7007 and starts with
`node packages/backend --config platform/entra.yaml`. It includes
native [Microsoft sign-in](https://backstage.io/docs/auth/microsoft/provider/),
[Graph directory sync](https://backstage.io/docs/integrations/azure/org/), and
[GitHub App integration](https://backstage.io/docs/integrations/github/github-apps/).
Direct Entra sign-in needs no Keycloak deployment.

The examples below reuse PostgreSQL, TLS termination, and secret injection.
The client owns backups and monitoring. Use the native
`/.backstage/health/v1/readiness` check through the existing runtime. On Kubernetes,
set `automountServiceAccountToken: false`: scaffolding needs no cluster credentials,
and the upstream app otherwise enables optional Kubernetes plugins when it finds
the token.

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
registry, and PostgreSQL.

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

Override lab template defaults with the same `NAME=value` pairs used by the CLI:

```bash
export PORTAL_SET='OWNER=team-payments AWS_REGION=eu-west-1 TOOLKIT_REPOSITORY=acme/developer-platform-kit TOOLKIT_REF=PUBLISHED_COMMIT_SHA'
make portal-up
```

Replace `PUBLISHED_COMMIT_SHA` with a full commit SHA containing these modules,
or an immutable release tag. `PORTAL_SET` also accepts other declared template
values such as `STATE_BUCKET`. Keep it in your shell environment for subsequent
updates; omit it to use the demo defaults. Git publishing destinations still use
`make portal-github OWNER=your-github-owner`.

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
terms with upstream before distributing its source or a client image. Dependency
licenses and the upstream README remain in the image.

General fixes to take upstream, with a reproduction against the pinned revision:

| Destination | General fix | Local evidence |
|---|---|---|
| `cnoe-io/stacks` | Keycloak bootstrap: architecture-aware kubectl, resume until client secrets exist, and avoid shell tracing credentials | `platform/keycloak/setup.patch` |
| `cnoe-io/backstage-app` | Register native GitHub actions for GitHub App integrations, not only when `GITHUB_TOKEN` exists; resolve Keycloak users by stable OIDC subject | `platform/backstage/source.patch` |
| Backstage scaffolder | Reproduce plain `DENY` being ignored for task lists in pinned 3.4.0; remove the empty-owner workaround once an adopted release enforces it | `platform/backstage/policy.cjs`, `platform/verify.py` |

Report the Terraform viewer's server file-read exposure through upstream's
security reporting channel; it remains disabled here. The missing CNOE app
license also needs an upstream answer. These are identified follow-ups, not
claims that reports have been submitted. Keep this kit's templates, delivery
choices, demo groups, and client-specific configuration here.

For distribution, original CLI/template/module code remains MIT with its notices;
the CNOE stacks checkout retains Apache-2.0. Missing app redistribution terms block
shipping the assembled portal image/source, not the standalone original-code CLI.
Review dependency notices when assembling a distributable image. Repository
access and the absence of a published release remain separate distribution
limitations for outside developers.

### Infrastructure boundaries

The infra starter selects its AWS capabilities from `services` and `data_pipelines`.
Empty workload maps create only the delivery role. Workloads add networking and
ECS; a public service adds the ALB; database consumers add PostgreSQL; pipelines
add migration tasks, storage, and Spark. No separate feature switches are needed.
Follow its README for state and identity setup. Keep plan/apply roles separate,
plan artifacts private and short lived, and database credentials in Secrets Manager.

Unused ECS scheduling, autoscaling, and service-discovery options are omitted.
Existing generated repos remain pinned to their module revision. When adopting
this starter, preserve `moved.tf`, review the plan for removed capabilities, and
update callers: ECS services no longer take `cluster_name`, clusters no longer
take `vpc_id`, and jobs no longer take `cluster_id` or `subnet_ids`. A stack using
the removed optional features must retain its previous module ref until migrated.

The starter supports one public service and ALB target group. Terraform owns
service shape; delivery owns task revisions. Images must match the X86_64 task
default. Spark requires fresh output paths; use run-specific prefixes and design
promotion in the consuming repo. Azure/GCP delivery is not implemented.

## Contribute

Bug fixes, clearer setup instructions, tests, and native integration improvements
are welcome. Small fixes can go straight to a pull request; describe the problem,
the change, and the checks run. For bug reports, include a reproduction and expected
behavior. Discuss a new audience or runtime target in an issue before implementing it.

Original contributions are accepted under [MIT](LICENSE); contributors retain
their copyright. Preserve licenses and notices for code from other projects.

For a first change, get repository access and clone it (or your accessible fork),
create a branch, and install the locked development tools:

```bash
git switch -c fix/describe-the-change
uv sync --frozen
make test                   # Fast gate: render all starters and check contracts
make lint-python
```

This path needs Python 3.13+ and uv; no AWS account or portal. For the complete
toolchain, install Docker and VS Code's Dev Containers extension, open this
checkout, and choose **Dev Containers: Reopen in Container**. The checked-in
`.devcontainer/` supplies the pinned tools and installs Git hooks. Locally,
use the versions in its Dockerfile and `.github/workflows/ci.yml`.

Keep a pull request focused on one observed problem. Edit the source template,
not an example render; render into a temporary directory and inspect the result.
Use the following checks in addition to `make test`:

| Change | Relevant checks |
|---|---|
| README/setup | Run the commands you changed; check rendered README text |
| Renderer, packaging, or template files | `make lint-python cli-check`; app/data: run generated lint/tests with `uv sync --locked` |
| Workflows | `make lint-workflows`; run the affected credential-free build path |
| Terraform modules or infra starter | `make validate-templates validate-modules lint-terraform lint-tflint lint-checkov` |
| Hosting or portal | `make hosting-check portal-check`; live identity/publishing checks below when affected |

Run `make check` and `make secret-scan` before requesting review when the full
toolchain is available. `make check` covers the kit's local gates without a cloud
account; hosted CI additionally audits dependencies and builds/tests the Backstage
image. A missing tool or unavailable service means a check **could not run**;
report that separately from a check that ran and failed. CI must pass before merge.

Commit the focused change, push your branch, and open a pull request against
`main`. Include the reproduction or use case, resulting behavior, checks and
their outcomes, and any remaining limitation. Private-fork availability depends
on repository policy; contributors with write access can use a branch in this
repository. Do not include generated environments, credentials, or build artifacts.

CI installs the wheel and source archive away from the checkout and compares
every rendered file and Backstage export (`make cli-check`). It tests generated
Python repositories with their locks. `make hosting-check` validates Compose and
CloudFormation without deploying. `make portal-check` also boots the actual Compose
service against disposable PostgreSQL with verified TLS and a non-superuser,
without external identity calls. Changes affecting
sign-in or publishing also need `portal-up`, `portal-verify`, and `portal-smoke`
with the local Gitea profile. Update upstream pins and patches together.

### Repository conventions

This kit owns scaffolding and shared delivery. Keep three templates and three
lanes: app, infra, and data. Prefer native integrations and declarative
configuration; custom code needs a verified gap and a current consumer. Keep user
and contributor documentation in this README and the generated READMEs.

| Path | Responsibility |
|---|---|
| `repo-templates/<name>/template.json` | Variable definitions with descriptions, examples, and patterns; no environment values or account IDs |
| `repo-templates/<name>/files/` | The generated repository tree, supported by both CLI and Backstage export; no kit-only files |
| `.github/workflows/reusable-*.yml` | One delivery lane per audience, called by ref; no stack names, regions, or cluster names |
| `.github/workflows/ci.yml` | This kit's checks; no cloud-account access |
| `modules/aws/<name>/` | One capability with a template caller; no stack wiring or workload identity |
| `scaffold/` | Rendering logic; template content belongs in templates |
| `platform/` | Upstream CNOE deployment, native integrations, overlays, and explicit patches; no duplicate templates or custom portal server |
| `tests/` | Rendering and delivery contracts; no production code |

- **Rendering:** `make test` is the gate. Declare `__UPPER_SNAKE__` tokens in
  `template.json`; undeclared tokens must fail with the file named. Compute derived
  values rather than declaring them: every `*_NAME` yields `*_SLUG`.
- **Delivery:** each lane has a `mode` input and one job per mode, gated by
  `if: inputs.mode == '...'`. Modes are mutually exclusive. Build never deploys;
  plan never applies. Apply verifies the plan run succeeded on the default branch
  and planned the current head. Reject `latest` in the lane and use immutable tags.
- **Credentials and evidence:** credentials arrive through `secrets:`, never
  `inputs:`. Every cloud-changing mode writes `release-event.json` inline with
  `jq`, without requiring a script from this kit. Irreversible changes require a
  literal `confirm`. Pin third-party actions to full SHAs with versions in trailing
  comments.
- **Modules:** include `main.tf`, `variables.tf`, `outputs.tf`, and `versions.tf`,
  with descriptions for every variable and output. Accept `name` and `tags`, and
  derive resource names from `name`. Enforce cost and data safeguards with
  `validation` and `precondition`; explain other choices in comments. Remove
  modules that have no template caller.
- **Upstream ownership:** keep the pinned CNOE checkout and generated packages
  ignored under `platform/.local/`. Preserve upstream licenses and remove local
  workarounds when upstream supplies the capability. Never commit credentials.
- **Errors and checks:** distinguish a failed task, a task that never started,
  and a rollout still in progress; each needs its own next step. Add tests for
  behavior changes. The test suite discovers templates and modules, so a new one
  should use those existing checks.

Avoid application/domain/schema code owned by the kit, custom control planes or
catalog servers, provider-neutral module wrappers, and runtime targets without
consumers. Remove redundant setup and speculative features.

### First contributions

Three small contributions address current gaps:

1. **Friendly manifest errors:** malformed JSON in `template.json` currently
   escapes as a traceback. Report the manifest path and JSON error through
   `TemplateError`, with a regression test showing no output files are written.
2. **Windows CLI smoke check:** installed-package CI currently runs only on
   Ubuntu. Add a focused Windows job that builds the package and runs
   `tests.validate_package`, without requiring Docker or Terraform.
3. **Data report tests:** the data starter tests quality outcomes but not
   `pipeline.main.write_report`. Test local nested-directory creation and the
   S3 bucket/key/body arguments using a fake client, without AWS or a Spark session.

## License

Original code is licensed under [MIT](LICENSE): you may use, modify, and redistribute
it, including commercially, while retaining its copyright and license notice.
Generated starters include that notice in `NOTICE`; teams choose the terms for
their own additions. Upstream dependencies retain their own licenses, including
Apache-2.0 where applicable. The [CNOE redistribution limitation](#upstream-ownership)
still applies.
