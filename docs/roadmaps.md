# Roadmaps

Use this file as the roadmap index and continuation guide. Individual roadmap
files keep phase history; this page keeps the cross-session rules in one place.

## Active Tracker

- [V5 roadmap](ROADMAP_V5.md) is the current tracker for production incident
  drills, rollout verification, async event processing, and documentation
  consolidation.

## History

- [V4 roadmap](ROADMAP_v4.md) is completed architecture comparison and
  production-grade slice history.
- [V3 roadmap](ROADMAP_V3.md) is completed modular monorepo and data-flow
  history.
- [V2 roadmap](ROADMAP_V2.md) is completed SDLC and migration hardening
  history.
- [V1 roadmap](ROADMAP.md) is completed baseline history.

## Continuation Rules

1. Read the active roadmap before changing DevOps, infrastructure, data-flow,
   observability, security, incident, rollout, async, or operator workflows.
2. Check `git status --short` before editing and preserve user-owned worktree
   changes.
3. Pick one coherent unchecked roadmap item or one newly discovered high-value
   operator slice.
4. Make the smallest complete change, verify it, update the active roadmap, and
   commit only the related files.

## Documentation Ownership

- `README.md` is the short project index.
- `docs/roadmaps.md` is the roadmap index and continuation guide.
- `docs/ROADMAP_V5.md` is the current progress tracker.
- Older `docs/ROADMAP*.md` files are historical records.
- `docs/deployment.md` is the detailed AWS operator runbook.
- `docs/local-development.md` is the local migration walkthrough.
- `docs/architecture.md` keeps long-form rationale and intentionally omitted
  hardening work.
- `docs/observability.md` explains Prometheus, Loki, Grafana, and CloudWatch
  signals.
- New `ops/` or `security/` files should appear only with concrete owned
  content.
