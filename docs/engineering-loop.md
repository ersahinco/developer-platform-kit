# Engineering Loop

Use this guide when continuing the project. The goal is to move like an
operator-engineer: inspect what exists, change the smallest useful slice,
deploy deliberately, observe the real system, repair drift, and leave the repo
clearer than you found it.

Use [Ubiquitous Language](ubiquitous-language.md) for names and boundaries
before adding new terms. The docs should give coding agents and humans the same
words for ideation, architecture, implementation, delivery, and operations.
Use the lean review below when the slice is mostly about reducing code,
dependency, documentation, or platform surface while preserving capability.

## Principles

- Lean: solve the real next problem and remove stale paths instead of adding
  parallel explanations or speculative components.
- Backward compatible: preserve working APIs, data paths, deploy flows, and
  operator commands unless the roadmap explicitly calls for a breaking change.
- Mindful: read the surrounding code and docs before changing them; consider
  who will debug, deploy, or pay for the thing later.
- Secure: keep secrets out of files and logs, prefer short-lived identity,
  preserve least-privilege IAM, and run secret scanning before committing.
- Reliable: favor reversible rollout steps, health checks, runbooks, and
  observable failure modes over clever one-way changes.
- Cost effective: keep default AWS resources small, optional, and owned by the
  right Terraform root; add spend only when it buys a clear operating signal.
- Not overengineered: use boring platform patterns and established tools before
  custom abstractions, extra services, or new frameworks.
- No dead paths: remove or update stale code, docs, tests, scripts, workflows,
  and path filters in the same slice that makes them obsolete.
- Organized by control boundary: keep GitHub workflows split by responsibility
  (`app-build`, `app-deploy`, `infra-plan`, `infra-apply`, `security`,
  `semgrep`) and Terraform split by lifecycle (`infra/platform` for bootstrap
  resources, `infra/app` for workload-owned resources). This is how the repo
  controls complexity without hiding it.
- Conventional where useful: keep root files that standard tools discover
  automatically at root, such as `compose.yaml`, `pyproject.toml`, `uv.lock`,
  `Makefile`, and `.dockerignore`. Group supporting assets under owned folders
  such as `observability/`, `db/`, and `.devcontainer/`.

## Loop

1. Inspect first.
   Check `git status --short`, read the current roadmap, and inspect the files
   that own the behavior. Trust the codebase shape over old notes.

2. Choose one slice.
   Prefer a complete vertical step over broad partial work. Keep AWS platform
   resources in `infra/platform`; keep app-owned RDS, ECS, ALB/API edge,
   workload resources, ALB access logs, and ADOT sidecar wiring in `infra/app`.

3. Build and verify locally.
   Use the narrowest checks that prove the change, then widen when the blast
   radius touches shared contracts. Do not skip formatting, secret scanning, or
   docs-link checks for repo-shape changes.

4. Deploy with state in mind.
   Use Terraform plans before applies. When AWS has partial resources or drift,
   prefer reconciliation through the owning root. Avoid targeted destroys unless
   the dependency graph is understood and the recovery path is immediate.

5. Observe before declaring done.
   Check ECS service rollouts, task events, logs, public health, CloudWatch
   alarms, and local/external Grafana signals that match the changed surface.
   CloudWatch stays in place for AWS-native rollback and managed-resource
   signals.

6. Fix the real failure.
   Use service events and logs to identify the owning layer. Patch the smallest
   durable cause, redeploy, then verify the system rather than only the code.

7. Leave less confusion.
   Update only canonical docs. Move or delete stale paths instead of preserving
   aliases that future work can accidentally follow. Keep code that encodes
   product/runtime truth; delete code that only compensates for unclear
   ownership.

## Documentation Rules

- `docs/roadmaps.md` tracks project work state: done, current, next, waiting,
  blocked, failed/recovered, and deferred.
- Durable explanations go in the relevant canonical doc, not in session notes.
- Runbooks live in `docs/runbooks/`; drills live in `docs/drills/`.
- Add a new runbook only when it describes an operator action someone can run.
- Keep examples executable and tied to current Terraform outputs or local
  Compose services.

## Lean Review

The rule is simple: keep code and docs that encode product/runtime truth; delete
code and docs that only compensate for unclear ownership.

Ask these before adding or keeping surface area:

1. Does this encode a durable product or runtime fact?
2. Is this the canonical owner, or is it repeating another file?
3. Can a proven standard tool own this behavior instead?
4. Does a workload, operator, or platform maintainer actually call this path?
5. Does the dependency belong in every image, or only in a specific job or
   optional extra?
6. Does the code make ownership clearer, or does it compensate for unclear
   ownership?
7. Can the rule be expressed as schema, tests, or a small contract instead of
   prose scanning or bespoke orchestration?

Treat these as prompts for review, not hard quotas:

| Signal | Review When |
|---|---|
| New runtime dependency | It is inherited by more than one image or duplicates a standard platform capability. |
| New workflow job | It repeats build, deploy, scan, or evidence logic already driven by metadata. |
| New Make target | It is an alias for a command with no ownership or operator value. |
| New Terraform resource group | It hand-wires a standard service that a module, sidecar, or managed service can own. |
| New top-level doc | It overlaps an existing canonical doc or restates project state. |
| New contract test | It protects machine-readable ownership, runtime behavior, or repo shape instead of exact prose. |
| Script over 200 lines | It orchestrates a tool that already has a CLI, module, or workflow primitive. |
| Doc over 300 lines | It mixes terms, current state, runbook actions, and architecture rationale. |

Run the narrowest checks that answer the question, then widen when the change
touches shared contracts or release paths:

```shell
git status --short
rg --files | wc -l
rg --files | xargs wc -l | sort -n | tail -30
rg --files | rg '(^docs/.*\.md$|^README\.md$)' | xargs wc -l | sort -n
rg -n "TODO|FIXME|deprecated|retired|legacy|temporary|workaround" README.md docs .github infra scripts tests
uv run python scripts/ci/validate_platform_contract.py
make lint-docs
uv run pytest tests/contracts -q
```

## Recovery Pattern

When a deploy goes sideways:

1. Name the symptom precisely.
2. Find the owner: platform, app Terraform, image/build, ECS task definition,
   runtime config, database, queue, or observability.
3. Stabilize the service if needed.
4. Reconcile the owning root.
5. Verify health, rollout state, logs, and metrics.
6. Commit the durable fix and record only the lasting lesson.
