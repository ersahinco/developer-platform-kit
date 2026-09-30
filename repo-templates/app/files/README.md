# __WORKLOAD_NAME__

Owned by __OWNER__. Scaffolded from the developer platform kit `app` template.

## Test locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run
these commands in this directory. uv supplies the Python version in
`.python-version`. No Docker, AWS account, or portal is needed for these checks.

```bash
uv sync --locked
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked pytest -v
```

To try the app, run `uv run --locked uvicorn app.main:app --reload --port __CONTAINER_PORT__`,
then open `http://localhost:__CONTAINER_PORT__/health`. Stop the server with Ctrl-C.
Commit `uv.lock` when intentionally changing dependencies.

## Contract

| Expectation | Lives in |
|---|---|
| `/health` is 200 while the process is alive | `app/main.py` |
| `/ready` is 503 until dependencies are usable | `app/main.py` |
| `/metrics` serves Prometheus text | `app/main.py` |
| Logs are JSON with `workload` and `environment` | `app/logging_setup.py` |
| Logging settings: `WORKLOAD_NAME`, `ENVIRONMENT`, `LOG_LEVEL` | `app/logging_setup.py` |
| Non-root image that forwards SIGTERM | `Dockerfile` |

`tests/` checks the endpoints and logging. The image build checks the Dockerfile.

## Delivery

`.github/workflows/delivery.yml`, calling the toolkit's app lane.

| Trigger | Does |
|---|---|
| Pull request | Lint, test, build, scan. Publishes nothing |
| Push to main | Lint, test, build, scan. Pushes `sha-<commit>` to ECR only when `PUBLISH_IMAGES=true` |
| Manual with a tag | Deploys that tag, waits for steady state, rolls back on failure |

Build and deploy are separate runs, so review happens between them. Deploy resolves the tag to a digest and refuses missing images. Restrict ECR write
permissions to the scanned build lane; existence alone does not prove scan provenance.

## First green CI

Push these files to `__REPOSITORY__` on branch `main` with GitHub Actions enabled.
Leave `PUBLISH_IMAGES` unset and add no AWS secrets. The **Delivery** run should
pass **Test** and **Build / Build & Scan**; deployment is skipped.

The shared workflow is pinned to `__TOOLKIT_REPOSITORY__` at `__TOOLKIT_REF__`.
GitHub must be able to read that revision. If the toolkit is private, its owner
must enable Actions access for eligible private caller repositories under the
same owner. Personal clone access alone does not grant workflow access.
A workflow resolution error means no jobs started: fix the reference or access.
If a job starts and fails, open that job's log and fix its reported test, build,
or scan error before retrying.

## Deployment prerequisites

Configure these only when ready to publish and deploy:

- repository secret `AWS_ROLE_ARN`; an `aws` environment with required reviewers and protected deployment branches
- variable `ECS_CLUSTER` from the infra repo's output
- repository variable `PUBLISH_IMAGES=true` to enable ECR publication on main pushes

The role needs OIDC trust for main-branch image publishing and the `aws`
environment for deployment, plus scoped ECR/ECS permissions. An AWS region in
the workflow is configuration, not a credential. Enabling publication makes
subsequent main pushes write to ECR; deploying remains a separate manual action.

The infra repo must already own the ECS service and task family named
`__WORKLOAD_NAME__` with a container named `app`, and the ECR repository
`__WORKLOAD_NAME__`. The deploy lane revises a service; it does not create one.
