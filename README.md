# Developer platform kit

A scaffolding capability for a developer platform: three repository starters,
three reusable CI/CD workflows, and a small Terraform module catalog. Teams own
and edit the generated repos. The toolkit adds no application runtime dependency.

```text
repo-templates/{app,infra,data}/   manifests and repository skeletons
.github/workflows/reusable-*.yml   one delivery lane per audience
modules/aws/                       representative IaC capabilities
scaffold/                          stdlib CLI and Backstage export
tests/                             rendering and delivery contracts
platform/                          CNOE assembly, native integrations, and live checks
```

## Start a repository

From this checkout with Python 3.13+, the renderer needs no installed packages:

```bash
python3 -m scaffold.new_repo list
python3 -m scaffold.new_repo describe app
python3 -m scaffold.new_repo render app ../orders-api \
  --set WORKLOAD_NAME=orders-api \
  --set OWNER=team-payments \
  --set REPOSITORY=acme/orders-api \
  --set AWS_REGION=eu-central-1 \
  --set TOOLKIT_REPOSITORY=ersahinco/developer-platform-kit \
  --set TOOLKIT_REF=14a28541b3c8bd8081651e5c07c22014c513d757
```

The example pins a published commit. Use a released tag or full commit SHA;
floating branches are rejected. `describe` shows
required variables and examples; rendering validates values before writing.
The CLI ends with files on disk. It does not create a GitHub repository, push a
commit, register a catalog entity, or start CI. Review the generated README, then
use Git/GitHub and Backstage's native registration when you want those steps.

| Starter | Repository contents | Delivery modes |
|---|---|---|
| `app` | Container host, health/readiness, Prometheus metrics, JSON logs, tests, dependency lock | `build`: test in the caller, build, scan, publish. `deploy`: release an existing image by digest |
| `infra` | Terraform root, state configuration, module composition, catalog metadata | `plan`: validate, lint, scan, save plan. `apply`: apply that reviewed plan |
| `data` | Spark ETL/ELT stages, JSON quality checks, Liquibase migrations, tests, dependency lock | `migrate`: run a published migration image. `pipeline`: package and execute Spark |

Each generated repo has one workflow for its lane and its own README. App build
and deploy share one reusable workflow; infra plan and apply share another.
Modes remain separate runs so review can happen between producing and releasing
an artifact. Data teams can remove the migration or Spark portion they do not need.

App and migration-image builds need no cloud credentials by default. Enable
ECR publication with the repository variable `PUBLISH_IMAGES=true` after configuring
AWS OIDC and the ECR repository. Published image tags are commit based,
and release resolves them to digests. Infra apply checks the source workflow,
successful default-branch plan, current head, state location, Terraform version,
and provider lock. Cloud-changing modes record `release-event.json`; apply and
data execution require explicit confirmation strings.

## Backstage

```bash
python3 -m scaffold.backstage /tmp/toolkit-backstage \
  --allowed-owner your-github-org \
  --set OWNER=team-payments \
  --set AWS_REGION=eu-central-1 \
  --set TOOLKIT_REPOSITORY=ersahinco/developer-platform-kit \
  --set TOOLKIT_REF=14a28541b3c8bd8081651e5c07c22014c513d757
```

Publish the exported directory to your template repository, then register its
`catalog-info.yaml` in an existing Backstage installation. Export derives forms
and skeletons from the CLI manifests, using native `fetch:template`, `publish:github`,
and `catalog:register` actions. Configure the GitHub integration and scaffolder
module in that portal.
See [Backstage Software Templates](https://backstage.io/docs/features/software-templates/writing-templates/).

Use `--provider gitea --base-url https://your-host/gitea` for a portal with
`publish:gitea`. Repeat `--allowed-owner` to permit multiple destinations; omitting
it permits any owner on the selected host. Exported task schemas enforce the host
and owner, including direct API requests. SCM credentials and portal permissions
must also restrict publishing access.

`--set` fixes platform-owned values in the exported template and removes them
from the developer form. Task parameters cannot override those values. Values
are validated against the same manifests as the CLI, which also accepts `--set`.
Add `--set STATE_BUCKET=your-existing-state-bucket` for infra; it does not add a
field to the other starters. Without `--set`, the exporter keeps the full forms.

To configure repository access and delivery automatically, pass
`--github-settings /path/to/client-github.json` with exactly one `--allowed-owner`.
The JSON uses the native GitHub action fields, keyed by `app`, `infra`, and `data`;
omit a starter to keep its basic publish/register flow. For example:

```json
{
  "app": {
    "collaborators": [{"team": "payments", "access": "push"}],
    "repoVariables": {"PUBLISH_IMAGES": "false", "ECS_CLUSTER": "existing-cluster"},
    "secrets": {"AWS_ROLE_ARN": "arn:aws:iam::123456789012:role/app-delivery"}
  }
}
```

Replace the example identifiers with existing client resources. Repository
variables must be consumed by that starter's workflow. The `secrets` field accepts
only IAM role ARNs, which are identifiers, not credentials; no access keys or
publishing tokens may enter these exported files. SCM credentials stay in
Backstage's integration configuration. A complete test example for all three
starters is in `tests/fixtures/github-settings.json`.

Configured starters use native `github:repo:create`, `github:environment:create`,
and `github:repo:push`: team access and delivery settings are applied before the
first commit starts CI. The `aws` environment permits only `main`; infra also
gets `aws-plan` for pull-request planning with a separate `AWS_PLAN_ROLE_ARN`.
The apply role must trust `aws`, the limited planning role `aws-plan`, and image
publication roles the repository's `refs/heads/main` subject. Do not give the
planning role permission to apply changes. These steps create no AWS resources;
ECR repositories, services, state, and roles must exist before their workflows
use them. Enable `PUBLISH_IMAGES=true` only after those targets are ready.

Install the native GitHub scaffolder module and grant the GitHub App the
[permissions for publishing, variables, secrets, and environments](https://backstage.io/docs/integrations/github/github-apps/#app-permissions).
The export configures environment branch restrictions; set the client's required
reviewers and approval rules in GitHub. Native
collaborator assignment can log a warning instead of failing the task, so confirm
team access during client acceptance. A failed setup can leave an empty repository;
inspect its task log before retrying. In the CNOE lab, the same configuration can
be placed in ignored `platform/.local/github-settings.json` before `portal-up`.

### Shared portal and self-service

Platform engineers can host one shared Backstage portal in the client's existing
container runtime. Developers sign in, choose a starter, enter project details,
and receive a repository and catalog entry. The CLI remains an alternative using
the same templates. The local CNOE deployment below is the integration lab;
shared hosting uses the image with the separate Entra configuration below and
the client's services and credentials.

The minimum client setup is Entra sign-in and team membership, a scoped GitHub
App, platform-owned template values, and delivery settings for existing AWS
targets. Backstage's native GitHub actions can assign repository collaborators,
set Actions variables and secrets, and create deployment environments. Configure
those before the first workflow runs using `--github-settings` above and the
client's team permissions and environment protection requirements. Basic exports
without those settings only publish and register repositories.

Keep the three identities separate: employees use their existing Entra/AWS
federation, GitHub Actions assumes a delivery role through OIDC, and workloads
use runtime roles. An employee's AWS access does not configure CI access. Reuse
existing roles, accounts, secret stores, certificates, and runtime targets;
creating another account or identity control plane is unnecessary.

### Run the reference platform locally

`platform/` assembles pinned [CNOE packages](https://cnoe.io/docs/reference-implementation/local)
for Kind, Gitea, Argo CD, Backstage, Keycloak, and External Secrets. It contains
deployment glue and live checks, separate from the templates exported to consuming
repos. CLI users and existing Backstage installations do not need it.

### Upstream ownership and customization

`platform/.local/stacks/` is an ignored clone of `cnoe-io/stacks`, checked out at
the full commit SHA in `platform/prepare.py`. Preparation leaves that checkout
unchanged and stages selected packages in `platform/.local/packages/`, retaining
the upstream license. These are disposable build outputs, not a maintained copy
of CNOE source. idpbuilder publishes the staging directories into local Gitea;
Argo CD reconciles them from there.

This repository owns the templates and the explicit configuration differences:
`platform/applications/` configures Argo applications, `platform/config/` overlays
Backstage, and `platform/keycloak/setup.patch` records the pinned bootstrap fixes.
Git rejects the patch if upstream context changes. Keep general fixes suitable
for upstream contribution; remove workarounds when an adopted upstream revision
includes them. To update CNOE, review the upstream changes, update the pin, run
`make portal-check`, then run the local deployment and live checks. Do not edit
the generated staging tree or commit the upstream clone.

The platform uses these upstream boundaries:

| Local code | Purpose and native boundary |
|---|---|
| `prepare.py` | Stages the pinned CNOE packages, exports this checkout's templates, and validates Kustomize overlays and the explicit Keycloak patch. |
| `identity.py` | Configures scopes, demo groups, and authenticated account linking through Keycloak's Admin API. Startup realm import skips an existing realm, so it cannot maintain this existing lab's settings. |
| `bootstrap.py` | Creates the local Gitea destination if absent and waits for Argo to observe the published Git revision. Backstage's native processing loop refreshes the catalog. Its sign-in helpers are used only by explicit live checks. |
| `runtime.py` | Supplies CA trust and native SCM integration credentials through Kubernetes resources. |
| `config/session-secret.yaml` | Uses External Secrets' native password generator for the persistent Backstage session key. |
| `backstage/` and `image.py` | Build pinned CNOE source with native Microsoft sign-in, Graph directory sync, and a group permission policy. A source patch selects the sign-in provider and fixes the local Keycloak subject; no compiled bundle is rewritten. |

These decisions are checked against the pinned
[CNOE packages](https://github.com/cnoe-io/stacks/tree/32160ecb5942b6d0199b1cef039cc3457d2b1100/ref-implementation),
[backend](https://github.com/cnoe-io/backstage-app/blob/6a5087c2fb6aeccdee5f2b5665f7d93cb89640b3/packages/backend/src/index.ts),
[resolver](https://github.com/cnoe-io/backstage-app/blob/6a5087c2fb6aeccdee5f2b5665f7d93cb89640b3/packages/backend/src/plugins/auth.ts),
and [Keycloak import behavior](https://www.keycloak.org/server/importExport).

The Backstage Dockerfile pins the CNOE source archive and Node image by digest,
applies `backstage/source.patch`, and installs with the patched upstream lockfile.
Dependency licenses and the upstream README remain in the image. This CNOE app
revision has no top-level license file; clarify its redistribution terms with
upstream before distributing a client image. The patch registers native providers
and our permission policy instead of guest sign-in and allow-all permissions.
Client authorization rules are normal Backstage composition; the local Keycloak
subject fix remains an upstream gap. The unused upstream Terraform viewer is
unregistered because it exposes server file reads and has no starter consumer.
The pinned scaffolder 3.4.0 task-list path ignores a plain permission `DENY`;
our policy uses its native empty task-owner condition for non-creators, so both
listing and individual task reads are restricted. The live check covers both.
Remove that compatibility condition when the adopted upstream version handles
`DENY` on task lists correctly.
Update the source pin and patch together,
then run `portal-check` and live checks before adopting an upgrade.

### Run the platform

Install Docker, Python 3.13+, kubectl,
Kind, and idpbuilder (verified with 0.10.2), then run from the repository root:

```bash
make portal-up              # Start or update the local deployment
make portal-check           # Assemble overlays and build/test the image without deploying
make portal-status          # Argo applications and Backstage pods
make portal-credentials     # Show local login passwords in your terminal
make portal-verify          # Identity, TLS, destination and group enforcement
make portal-smoke           # Create all three starters in local Gitea
```

`portal-up` builds the CNOE Backstage integration, loads it into the `toolkit`
Kind cluster, and republishes templates from this checkout. The native
[catalog processing loop](https://backstage.io/docs/features/software-catalog/configuration/#processing-interval)
uses a 30-second minimum interval; allow about a minute for template changes to
appear. Startup does not sign in as a demo user. Backstage builds for the host's
architecture, including ARM. State, kubeconfig, and credentials are ignored
under `platform/.local/`; your default kubeconfig is not modified.

The first source build downloads and compiles upstream dependencies and takes
several minutes; later builds reuse Docker's cache. The build and running lab
were checked with 12 GB allocated to Docker. Developers using a shared portal
do not need this local stack; CLI rendering requires only Python.

When updating an older checkout, move `local/.local/` to `platform/.local/`
before starting the platform to preserve its kubeconfig and integration settings.
The existing idpbuilder cluster also retains absolute repository source paths.
After `make portal-prepare`, update those four paths once, then run `make portal-up`:

```bash
for package in external-secrets keycloak backstage backstage-templates; do
  directory=manifests
  [ "$package" != backstage-templates ] || directory=entities
  kubectl --kubeconfig platform/.local/kubeconfig -n idpbuilder-toolkit \
    patch gitrepository "$package-$directory" --type=merge \
    -p "{\"spec\":{\"source\":{\"path\":\"$PWD/platform/.local/packages/$package/$directory\"}}}"
done
```

External Secrets takes over the previous session secret on the first rollout;
sign in again afterward. Its zero refresh interval prevents periodic regeneration.

If the final bootstrap wait times out, `make portal-status` shows Argo's
conditions as well as pod readiness. A healthy Backstage pod does not prove Argo
can read the template repository; for example, a `ComparisonError` with a DNS
timeout means reconciliation is blocked. Resolve the reported cause, then run
`python3 platform/bootstrap.py` to repeat the final check without rebuilding the platform.

CNOE supplies Backstage and Keycloak. `platform/config/` uses native
[Kustomize overlays](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)
and [Backstage configuration layers](https://backstage.io/docs/conf/writing/)
for TLS, credentials, catalog sources, and deployment settings. `portal-prepare`
validates the overlay; Argo CD applies it and prunes obsolete resources after
healthy rollout. No second portal or identity server is added. The source patch
keeps the local Keycloak subject stable and connects verified groups; remove that
resolver change when upstream supplies it. The pinned Keycloak setup job also needs
compatibility fixes for ARM, resumable setup, and secret-safe logging. These
workarounds stay limited to the local reference; the renderer and templates do
not depend on them. CI runs `portal-check`, including the image's permission and
identity tests and native GitHub actions against an offline API double. Live
sign-in and deployment checks remain explicit local commands.

Open [Backstage](https://cnoe.localtest.me:8443) and use `user1` with the
`USER_PASSWORD` shown by the credentials command. Choose **Create**, select a
starter, and provide a unique repository name under the default `platform` Gitea
owner. To manage identities, open the
[Keycloak admin console](https://cnoe.localtest.me:8443/keycloak/admin/), sign in as
`cnoe-admin` with `KEYCLOAK_ADMIN_PASSWORD`, and select the `cnoe` realm.

| Local user | Keycloak group | Allowed |
|---|---|---|
| `user1` | `scaffold-creators` | Browse, scaffold, read/cancel tasks, register components |
| `user2` | `scaffold-viewers` | Browse catalog and template listings; cannot open creation forms |

Both users share the local `USER_PASSWORD`; `portal-up` manages their scaffold
groups. Sign in again after membership changes; issued tokens retain claims until
expiration. The backend denies unknown permissions, unrecognized groups, and
viewer writes even if the older UI shows a control. Creators are trusted catalog
contributors, with access to the four native render/publish/register actions.

`portal-credentials` displays only the two Keycloak login passwords. It does not
display database credentials or SCM tokens. Keep its output in your terminal.

`portal-verify` checks real sign-ins, denied writes, membership removal and
restoration, destination validation, TLS trust, and restricted cluster access.
`portal-smoke` creates three local repositories and compares every file with CLI
output; it refuses the GitHub profile to avoid external test repositories.
Gitea uses server-default repo visibility and does not execute the generated GitHub
Actions workflows. GitHub publishing creates private repos. The lab deploys no
cloud resources; scaffold groups grant no cloud access.

No domain purchase is needed. `portal-up` exports the public local CA to
`platform/.local/platform-ca.crt`; Backstage trusts it explicitly. Import it into
your workstation trust store yourself to trust the local browser endpoint.
Replace that trust if you delete and rebuild the cluster. Do not distribute the
CA private key. This lab uses upstream demo images and shared local credentials;
shared production hosting needs maintained images, scoped identities, backups,
and its own deployment configuration. Delete only this lab, including its local
repositories, with `make portal-down`.

### Connect personal GitHub

Sign-in and repository publishing are separate native integrations. Local Keycloak
login already works; external sign-in is optional for publishing.

1. Register a [GitHub OAuth App](https://github.com/settings/applications/new)
   with homepage `https://cnoe.localtest.me:8443` and callback
   `https://cnoe.localtest.me:8443/keycloak/realms/cnoe/broker/platform-github/endpoint`.
2. Run `make portal-identity PROVIDER=github`; enter the client ID and hidden
   client-secret prompt. `google` and `microsoft` also use native Keycloak providers;
   those commands print their callback before prompting. Personal Microsoft
   accounts require a client registration supporting personal accounts.
3. Choose the provider on the Keycloak sign-in page. On first login, authenticate
   as an existing local user to link accounts. Neither email matching nor a new
   external identity automatically creates or links a local user.

External sign-in needs browser verification. The lab resolves identity from the
standard OIDC `sub` claim (the immutable Keycloak user ID), following
[Backstage's OIDC resolver example](https://backstage.io/docs/auth/oidc/).
It no longer rewrites Keycloak's realm-wide `name` claim. Existing realm mappers
are preserved; they are no longer needed for identity resolution. Enterprise
portals should use their native catalog identity resolver.

For publishing:

```bash
make portal-github OWNER=ersahinco
make portal-up
make portal-verify
```

The first command accepts a dedicated, expiring token through a hidden prompt;
it never reuses your `gh` credential. A
[fine-grained token](https://github.com/settings/personal-access-tokens/new)
for the destination owner needs repository **Administration**, **Contents**, and
**Workflows** write permissions for the native publisher and generated workflows.
Choose **All repositories** for this one-step create-and-push flow: selecting only
existing repositories cannot include the repository that has not been created yet.
A classic token with `repo` and `workflow` is an alternative. Organization policies
may impose additional restrictions; see
[GitHub token permissions](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

The native `integrations.github` config is saved in ignored
`platform/.local/backstage-integrations.json` with mode `0600` and mounted as a
Kubernetes Secret. `platform/.local/github-owner` selects the destination. Run
`portal-up` after changes. Credentials never enter exported templates; do not
paste them into tracked files or chat.

Choose **Create → platform-app** and submit a unique name to verify real GitHub
publishing and catalog registration. Its initial CI run tests, builds, and scans;
leave `PUBLISH_IMAGES` unset during a demo. GitHub publishing credentials do not
authorize AWS image publication or deployment. If the toolkit repository is
private, its **Settings → Actions → General → Access** must permit calls from
the destination's private repositories; see
[GitHub's private-workflow sharing](https://docs.github.com/en/actions/how-tos/reuse-automations/share-across-private-repositories).
Otherwise the workflow cannot start, even when publishing succeeded. Repository
publishing, catalog reading, and reusable-workflow access are separate permissions.
For an organization, prefer
Backstage's native [GitHub App integration](https://backstage.io/docs/integrations/github/github-apps/):
put its native integration config in the same ignored file, install it in the
organization, set `platform/.local/github-owner`, and run `make portal-up`.
Enterprise deployments should source credentials through External Secrets and
an existing secret store. To return to Gitea, remove the GitHub owner, integration,
and optional settings configuration
files, run `make portal-up`, and revoke the unused publishing token in GitHub.

### Connect existing enterprise services

| Capability | Reuse | Current boundary |
|---|---|---|
| Employee identity | [Backstage Microsoft provider](https://backstage.io/docs/auth/microsoft/provider/) and [Microsoft Graph catalog provider](https://backstage.io/docs/integrations/azure/org/) | The image includes both native modules and a Microsoft sign-in page. Supply the client's registration and group configuration below. A personal Outlook account is not an enterprise directory. |
| Repository publishing | [GitHub integration](https://backstage.io/docs/integrations/github/github-apps/) | Native publishing and repository/environment actions; organization GitHub App or a dedicated personal-account token. Sign-in credentials and publishing credentials are separate. |
| GitLab | [Native GitLab integration](https://backstage.io/docs/integrations/gitlab/locations/) | Integration point for an existing portal; this toolkit does not yet export GitLab CI or GitLab publishing templates. |
| Secrets | [External Secrets](https://external-secrets.io/latest/provider/azure-key-vault/) | Portal deployment references an existing secret store. Secrets never enter rendered repositories. |
| TLS | [cert-manager issuers](https://cert-manager.io/docs/configuration/) and [trust-manager](https://cert-manager.io/docs/trust/trust-manager/) | Reuse an existing issuer and distribute its CA bundle. Workstation trust is separate from Kubernetes trust. |

These settings belong to the shared portal deployment. Use an existing Backstage
installation, or build `platform/backstage` and host the resulting image in the
client's runtime. It listens on port 7007 and defaults to
`node packages/backend --config platform/entra.yaml`; the CNOE lab overrides that
command with its Keycloak configuration. Keycloak is unnecessary for direct Entra
sign-in. Supply PostgreSQL, TLS termination, secret injection, backups, and the
native `/.backstage/health/v1/readiness` health check through the existing runtime.
On Kubernetes, set `automountServiceAccountToken: false`, as the local overlay
does. This portal's scaffolding flow needs no cluster credentials; the upstream
app otherwise detects the token and enables its optional Kubernetes plugins.

The image's `platform/entra.yaml` comes from `platform/backstage/entra.yaml` here.
Provide these values through the client's runtime and secret store:

| Values | Purpose |
|---|---|
| `PORTAL_URL` | External HTTPS URL of this portal |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DATABASE`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Existing PostgreSQL database; the user needs permission to create schemas inside it, not create databases |
| `SESSION_SECRET` | Persistent random session key, shared across portal replicas |
| `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET` | Tenant-specific Web application registration |
| `ENTRA_CREATORS_GROUP_ID`, `ENTRA_VIEWERS_GROUP_ID` | Existing directory groups to import, together with their direct user members |
| `ENTRA_CREATORS_GROUP_REF`, `ENTRA_VIEWERS_GROUP_REF` | Imported Backstage group refs, e.g. `group:default/platform-creators`; native Graph uses normalized group names, not group IDs |
| `GITHUB_APP_ID`, `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_ORGANIZATION` | Scoped native GitHub App integration; the pinned integration requires its client ID and secret as well as the signing key |
| `TEMPLATES_CATALOG_URL` | Published `catalog-info.yaml` from this kit's export |

Register `PORTAL_URL/api/auth/microsoft/handler/frame` as the Entra Web redirect
URI. Grant the native provider's delegated sign-in permissions and the directory
provider's application permissions (`User.Read.All`, `GroupMember.Read.All`), with
tenant consent. Directory sync runs every 15 minutes. Confirm imported group refs
against their `graph.microsoft.com/group-id` annotations and update the configured
refs if groups are renamed. Set exported `OWNER` to the owning group's catalog
name. Only configured template locations may supply executable templates;
developers can register their generated components.

The native resolver matches `graph.microsoft.com/user-id` and requires a catalog
user. It has no email-based or missing-user fallback. PostgreSQL certificate
validation stays enabled; mount the client's CA and set `NODE_EXTRA_CA_CERTS` when
using a private issuer. Do not copy the local lab's users or credentials into the
shared deployment. Live client sign-in, consent, team access, and AWS delivery
must be verified with the client's services. GitLab delivery is not implemented.

## IaC catalog and cloud boundaries

`modules/aws/` contains `network`, `ecr`, `github-oidc`, `ecs-cluster`, `alb`,
`ecs-service`, `ecs-job`, `postgres`, `object-storage`, and `emr-serverless`.
Each has a caller in the infra starter and documented inputs/outputs in HCL.

The shipped implementation is **AWS ECS/Fargate and EMR Serverless**. Multi-cloud
standardization here means the same ownership, repository, artifact, approval,
and evidence contracts. Azure/GCP delivery is not implemented. Add provider-specific
modules and concrete lane implementations when there is a consuming team; keep
provider identity and state explicit instead of inventing neutral resource wrappers.

Before the first apply, remove unused capabilities from the infra starter and
review its billable resources. Follow its README to bootstrap state and identity.
Production roles should be distinct per repo and per plan/apply privilege, with
protected environments and branch restrictions. Plans can contain secrets: keep
artifacts private and short lived. Database credentials stay in Secrets Manager.

The starter has one ALB target group and permits one public service. Terraform
owns service shape; delivery owns task revisions. Workload images must match the
X86_64 task default. Spark refuses existing output paths; use run-specific prefixes
and design dataset promotion in the consuming repo.

## Contribute

```bash
make help
make check
```

The gate renders all three starters, checks workflow contracts and Python types,
validates every module and the rendered infra root, and runs TFLint, Checkov, and
Dockerfile linting. CI also runs each generated Python repo's tests with its lock.
Checkov exceptions stay next to the affected resources with reasons.
`.devcontainer/` installs the tools used by these checks. `AGENTS.md` defines editing
rules; `catalog-info.yaml` registers the toolkit itself in Backstage. Keep user
documentation here and in each generated repo's README.
