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
local/                             run and verify Backstage/Keycloak through CNOE
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
  --set TOOLKIT_REF=v0.1.0
```

Replace `v0.1.0` with a published release tag or full commit SHA; the example
does not imply a release exists. Floating branches are rejected. `describe` shows
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
python3 -m scaffold.backstage /tmp/toolkit-backstage --allowed-owner your-github-org
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

### Run the reference platform locally

`local/` assembles pinned [CNOE packages](https://cnoe.io/docs/reference-implementation/local)
for Kind, Gitea, Argo CD, Backstage, Keycloak, and External Secrets. It contains
deployment glue and live checks, separate from the templates exported to consuming
repos. CLI users and existing Backstage installations do not need it.

The local assembly uses these upstream boundaries:

| Local code | Purpose and native boundary |
|---|---|
| `prepare.py` | Copies the pinned CNOE packages, exports this checkout's templates, and applies Kustomize configuration. The pinned Keycloak job needs architecture and secret-logging fixes, plus a completed-setup check. |
| `identity.py` | Configures scopes, demo groups, and authenticated account linking through Keycloak's Admin API. Startup realm import skips an existing realm, so it cannot maintain this existing lab's settings. |
| `bootstrap.py` | Creates the local Gitea destination if absent and waits for Argo to observe the published Git revision. Backstage's native processing loop refreshes the catalog. Its sign-in helpers are used only by explicit live checks. |
| `runtime.py` | Supplies CA trust, a persistent session key, and native SCM integration credentials through Kubernetes resources. |
| `backstage/` and `image.py` | Supply the missing native permission backend and connect verified OIDC identity/group claims. The pinned backend does not register the permission plugin; YAML alone cannot add it. |

These decisions are checked against the pinned
[CNOE packages](https://github.com/cnoe-io/stacks/tree/32160ecb5942b6d0199b1cef039cc3457d2b1100/ref-implementation),
[backend](https://github.com/cnoe-io/backstage-app/blob/9232d633b2698fffa6d0a73b715e06640d170162/packages/backend/src/index.ts),
[resolver](https://github.com/cnoe-io/backstage-app/blob/9232d633b2698fffa6d0a73b715e06640d170162/packages/backend/src/plugins/auth.ts),
and [Keycloak import behavior](https://www.keycloak.org/server/importExport).

Install Docker (at least 6 GB memory), Python 3.13+, kubectl,
Kind, and idpbuilder (verified with 0.10.2), then run from the repository root:

```bash
make portal-up              # Start or update the local deployment
make portal-status          # Argo applications and Backstage pods
make portal-credentials     # Show local login passwords in your terminal
make portal-verify          # Identity, TLS, destination and group enforcement
make portal-smoke           # Create all three starters in local Gitea
```

`portal-up` builds the native permission integration, loads it into the `toolkit`
Kind cluster, and republishes templates from this checkout. The native
[catalog processing loop](https://backstage.io/docs/features/software-catalog/configuration/#processing-interval)
uses a 30-second minimum interval; allow about a minute for template changes to
appear. Startup does not sign in as a demo user. The pinned CNOE image
requires AMD64 emulation on ARM. State, kubeconfig, and credentials are ignored
under `local/.local/`; your default kubeconfig is not modified.

CNOE supplies Backstage and Keycloak. `local/config/` uses native
[Kustomize overlays](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)
and [Backstage configuration layers](https://backstage.io/docs/conf/writing/)
for TLS, credentials, catalog sources, and deployment settings. `portal-prepare`
validates the overlay; Argo CD applies it and prunes obsolete resources after
healthy rollout. No second portal or identity server is added. The pinned Backstage bundle needs
guarded code patches to use the OIDC subject, connect verified groups, and load its native permission
backend. This is the main maintenance compromise; remove those patches when the
upstream image supplies that wiring. The pinned Keycloak setup job also needs
compatibility fixes for ARM, resumable setup, and secret-safe logging. These
workarounds stay limited to the local reference; the renderer and templates do
not depend on them.

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
`local/.local/platform-ca.crt`; Backstage trusts it explicitly. Import it into
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
`local/.local/backstage-integrations.json` with mode `0600` and mounted as a
Kubernetes Secret. `local/.local/github-owner` selects the destination. Run
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
organization, set `local/.local/github-owner`, and run `make portal-up`.
Enterprise deployments should source credentials through External Secrets and
an existing secret store. To return to Gitea, remove the two GitHub configuration
files, run `make portal-up`, and revoke the unused publishing token in GitHub.

### Connect existing enterprise services

| Capability | Reuse | Current boundary |
|---|---|---|
| Employee identity | [Backstage Microsoft provider](https://backstage.io/docs/auth/microsoft/provider/) and [Microsoft Graph catalog provider](https://backstage.io/docs/integrations/azure/org/) | Install the native backend modules and frontend sign-in provider in your existing portal; select groups and resolve users by directory ID. A personal Outlook account is not an enterprise directory. |
| Repository publishing | [GitHub integration](https://backstage.io/docs/integrations/github/github-apps/) | Native `publish:github`; organization GitHub App or a dedicated personal-account token. Sign-in credentials and publishing credentials are separate. |
| GitLab | [Native GitLab integration](https://backstage.io/docs/integrations/gitlab/locations/) | Integration point for an existing portal; this toolkit does not yet export GitLab CI or GitLab publishing templates. |
| Secrets | [External Secrets](https://external-secrets.io/latest/provider/azure-key-vault/) | Portal deployment references an existing secret store. Secrets never enter rendered repositories. |
| TLS | [cert-manager issuers](https://cert-manager.io/docs/configuration/) and [trust-manager](https://cert-manager.io/docs/trust/trust-manager/) | Reuse an existing issuer and distribute its CA bundle. Workstation trust is separate from Kubernetes trust. |

Reuse existing enterprise services instead of installing this local lab. The
settings above belong to the portal deployment; CI uses separate cloud workload
identities. Live Entra and GitLab integration are not implemented here.

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
