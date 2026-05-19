@AGENTS.md

## Claude Code / Kiro — Additional Setup

The cross-tool base rules are in `AGENTS.md` above.
Kiro loads richer scoped rules from `.kiro/steering/` automatically.

### On-Demand Skills

Reference these in chat when the work type matches:

- `#skill-clean-architecture` — refactoring across `packages/`/`apps/` boundary
- `#skill-ddd` — domain modeling, aggregates, domain events
- `#skill-release-it` — services, health checks, Dapr, production reliability
- `#skill-ddia` — schema changes, outbox, backfill, idempotency
- `#skill-pragmatic-programmer` — general engineering, automation, tech debt
- `#skill-refactoring` — refactoring passes, module boundary cleanup

### Procedures and Long References

Use skills for long procedures and checklists — keep this file short.
Scoped rules for specific layers live in `.kiro/steering/`.
