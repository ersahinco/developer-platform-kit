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
```

## Start a repository

```bash
uv sync --frozen
uv run python -m scaffold.new_repo list
uv run python -m scaffold.new_repo describe app
uv run python -m scaffold.new_repo render app ../orders-api \
  --set WORKLOAD_NAME=orders-api \
  --set OWNER=team-payments \
  --set REPOSITORY=acme/orders-api \
  --set AWS_REGION=eu-central-1 \
  --set TOOLKIT_REPOSITORY=ersahinco/developer-platform-kit \
  --set TOOLKIT_REF=v0.1.0
```

Publish the tested toolkit revision first and substitute its actual release tag
or full commit SHA; the example does not imply a release already exists. Floating
branches are rejected. Each variable has an example, description, and validation
pattern. Names derive their slugs automatically. Rendering fails before writing
if an undeclared token remains or a path escapes the destination.

| Starter | Repository contents | Delivery modes |
|---|---|---|
| `app` | Container host, health/readiness, Prometheus metrics, JSON logs, tests, dependency lock | `build`: test in the caller, build, scan, publish. `deploy`: release an existing image by digest |
| `infra` | Terraform root, state configuration, module composition, catalog metadata | `plan`: validate, lint, scan, save plan. `apply`: apply that reviewed plan |
| `data` | Spark ETL/ELT stages, JSON quality checks, Liquibase migrations, tests, dependency lock | `migrate`: run a published migration image. `pipeline`: package and execute Spark |

Each generated repo has one workflow for its lane and its own README. App build
and deploy share one reusable workflow; infra plan and apply share another.
Modes remain separate runs so review can happen between producing and releasing
an artifact. Data teams can remove the migration or Spark portion they do not need.

PR app builds need no cloud credentials. Published image tags are commit based,
and release resolves them to digests. Infra apply checks the source workflow,
successful default-branch plan, current head, state location, Terraform version,
and provider lock. Cloud-changing modes record `release-event.json`; apply and
data execution require explicit confirmation strings.

## Backstage

```bash
uv run python -m scaffold.backstage /tmp/toolkit-backstage
```

Publish the exported directory to your template repository, then register its
`catalog-info.yaml` in an existing Backstage installation. Export derives forms
and skeletons from the same manifests as the CLI, using the native `fetch:template`,
`publish:github`, and `catalog:register` actions. Configure GitHub integration and
the GitHub scaffolder module there. No portal or custom action ships in this repo.
See [Backstage Software Templates](https://backstage.io/docs/features/software-templates/writing-templates/).

For a local CNOE portal backed by Gitea, export the same templates with:

```bash
uv run python -m scaffold.backstage /tmp/toolkit-gitea \
  --provider gitea --base-url https://cnoe.localtest.me:8443/gitea
```

The portal must supply `publish:gitea` and a matching Gitea integration. The CLI's
`REPOSITORY=owner/name` and optional `REPOSITORY_BASE_URL` describe the generated
repo; `TOOLKIT_REPOSITORY` and `TOOLKIT_REF` select the shared delivery source on
GitHub. Backstage derives the destination from its repository picker.

The companion `developer-platform-local` repository assembles pinned
[CNOE packages](https://cnoe.io/docs/reference-implementation/local) for Kind,
Gitea, Argo CD, Backstage, Keycloak, and External Secrets. It owns deployment and
local credentials; this toolkit owns scaffolding. Local Gitea publishing and
catalog registration do **not** enable delivery: the generated workflows still
require GitHub Actions and AWS. CNOE's bundled Gitea publisher uses server-default
repository visibility; the GitHub export explicitly creates private repos.

## IaC catalog and cloud boundaries

`modules/aws/` contains `network`, `ecr`, `github-oidc`, `ecs-cluster`, `alb`,
`ecs-service`, `ecs-job`, `postgres`, `object-storage`, and `emr-serverless`.
Every module takes `name` and `tags`, documents inputs/outputs in HCL, and has a
caller in the infra starter. Terraform 1.10+ supports the starter's S3 state lock;
the AWS provider is 6.x and the VPC registry module is pinned to 6.7.3.

The shipped implementation is **AWS ECS/Fargate and EMR Serverless**. Multi-cloud
standardization here means the same ownership, repository, artifact, approval,
and evidence contracts. Azure/GCP delivery is not implemented. Add provider-specific
modules and concrete lane implementations when there is a consuming team; keep
provider identity and state explicit instead of inventing neutral resource wrappers.
The container host, Spark stages, Liquibase changesets, and Backstage metadata can
move with that team.

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
Checkov exceptions are resource-local with reasons; they describe consumer choices
such as retention and availability, not a global disabled policy list.

Keep three audiences and three lanes. A fourth needs a real audience. Delete
uncalled modules, obsolete workflows, and unused template content. Keep prose
here and in the README that each template renders.
