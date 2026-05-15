# Engineering Loop

Use this guide when continuing the project. The goal is to move like an
operator-engineer: inspect what exists, change the smallest useful slice,
deploy deliberately, observe the real system, repair drift, and leave the repo
clearer than you found it.

Use [Ubiquitous Language](ubiquitous-language.md) for names and boundaries
before adding new terms. The docs should give coding agents and humans the same
words for ideation, architecture, implementation, delivery, and operations.
Use [Lean Profile](lean-profile.md) when the slice is mostly about reducing
code, dependency, documentation, or platform surface while preserving capability.

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

## Recovery Pattern

When a deploy goes sideways:

1. Name the symptom precisely.
2. Find the owner: platform, app Terraform, image/build, ECS task definition,
   runtime config, database, queue, or observability.
3. Stabilize the service if needed.
4. Reconcile the owning root.
5. Verify health, rollout state, logs, and metrics.
6. Commit the durable fix and record only the lasting lesson.
