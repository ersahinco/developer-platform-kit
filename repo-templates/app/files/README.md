# __WORKLOAD_NAME__

Owned by __OWNER__. Scaffolded from the developer platform kit `app` template.

## First

```bash
uv sync
uv run uvicorn app.main:app --reload --port __CONTAINER_PORT__
uv run pytest -v
```

## Contract

| Expectation | Lives in |
|---|---|
| `/health` is 200 while the process is alive | `app/main.py` |
| `/ready` is 503 until dependencies are usable | `app/main.py` |
| `/metrics` serves Prometheus text | `app/main.py` |
| Logs are JSON with `workload` and `environment` | `app/logging_setup.py` |
| Config from the environment, secrets injected at runtime | `app/config.py` |
| Non-root image that forwards SIGTERM | `Dockerfile` |

`tests/test_contract.py` enforces these. Change them deliberately.

## Delivery

`.github/workflows/delivery.yml`, calling the toolkit's app lane.

| Trigger | Does |
|---|---|
| Pull request | Lint, test, build, scan. Publishes nothing |
| Push to main | Lint, test, build, scan. Pushes `sha-<commit>` to ECR only when `PUBLISH_IMAGES=true` |
| Manual with a tag | Deploys that tag, waits for steady state, rolls back on failure |

Build and deploy are separate runs, so review happens between them. Deploy resolves the tag to a digest and refuses missing images. Restrict ECR write
permissions to the scanned build lane; existence alone does not prove scan provenance.

## Repository settings

The initial push needs no AWS credentials. Leave `PUBLISH_IMAGES` unset for a
demo or until the cloud resources and publishing role are ready.

- repository secret `AWS_ROLE_ARN`; an `aws` environment with required reviewers and protected deployment branches
- variable `ECS_CLUSTER` from the infra repo's output
- repository variable `PUBLISH_IMAGES=true` to enable ECR publication on main pushes

The infra repo must already own the ECS service and task family named
`__WORKLOAD_NAME__` with a container named `app`, and the ECR repository
`__WORKLOAD_NAME__`. The deploy lane revises a service; it does not create one.
