# Engineering Loop

Use this guide when continuing the project. The goal is to move like an
operator-engineer: inspect what exists, change the smallest useful slice,
deploy deliberately, observe the real system, repair drift, and leave the repo
clearer than you found it.

## Loop

1. Inspect first.
   Check `git status --short`, read the current roadmap, and inspect the files
   that own the behavior. Trust the codebase shape over old notes.

2. Choose one slice.
   Prefer a complete vertical step over broad partial work. Keep AWS platform
   resources in `infra/platform`; keep app-owned RDS, ECS, ALB/API edge,
   workload resources, and Grafana/Loki/Prometheus in `infra/app`.

3. Build and verify locally.
   Use the narrowest checks that prove the change, then widen when the blast
   radius touches shared contracts. Do not skip formatting, secret scanning, or
   docs-link checks for repo-shape changes.

4. Deploy with state in mind.
   Use Terraform plans before applies. When AWS has partial resources or drift,
   prefer reconciliation through the owning root. Avoid targeted destroys unless
   the dependency graph is understood and the recovery path is immediate.

5. Observe before declaring done.
   Check ECS service rollouts, task events, logs, public health, and the
   Grafana-stack/CloudWatch signals that match the changed surface. CloudWatch
   stays in place until matching Grafana-stack signals have dual-run.

6. Fix the real failure.
   Use service events and logs to identify the owning layer. Patch the smallest
   durable cause, redeploy, then verify the system rather than only the code.

7. Leave less confusion.
   Update only canonical docs. Move or delete stale paths instead of preserving
   aliases that future work can accidentally follow.

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
