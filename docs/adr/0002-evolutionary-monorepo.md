# ADR 0002: Evolutionary Monorepo Restructure

## Status

Accepted

## Context

The repository already has working app, worker, database, infrastructure,
scripts, tests, and CI/CD flows. A full restructure into `apps/` and
`packages/` would touch many paths at once and could obscure whether behavior
changed.

## Decision

Restructure the repository gradually. Add shared planning and documentation
first, then move app and worker code only in a dedicated phase with tests,
Docker Compose, Makefile, scripts, and GitHub Actions updated together.

## Consequences

- Future sessions have a shared roadmap before making structural changes.
- Runtime behavior remains stable during documentation and planning work.
- The eventual monorepo shape can be reached without sacrificing the current safe-rollout demo.
