# Agent Steering Rules

This directory contains Kiro steering files that guide AI agents working in this
platform monorepo. The goal is reliable, consistent, standardized output with
minimal technical debt — regardless of which agent session is running.

Rules are sourced from the platform's own contracts and from
[agent-rules-books](https://github.com/ciembor/agent-rules-books) (MIT licensed),
which distills classic engineering books into agent-readable rule sets.

---

## Multi-Tool Architecture

Each agent tool reads rules through its own native mechanism. The same content
is not duplicated — each layer serves a different tool:

```
AGENTS.md                    ← Codex (root + nested), OpenCode, Claude Code fallback
CLAUDE.md                    ← Claude Code / Kiro (imports @AGENTS.md)
.kiro/steering/              ← Kiro only (richer scoped layer, file-match auto-loading)
packages/AGENTS.md           ← Codex scoped to packages/ subtree
apps/AGENTS.md               ← Codex scoped to apps/ subtree
infra/AGENTS.md              ← Codex scoped to infra/ subtree
tests/AGENTS.md              ← Codex scoped to tests/ subtree
db/AGENTS.md                 ← Codex scoped to db/ subtree
.github/AGENTS.md            ← Codex scoped to .github/ subtree
opencode.json                ← OpenCode config (loads AGENTS.md; nested files auto-traversed)
```

**Why both `.kiro/steering/` and nested `AGENTS.md` files?**
- Kiro has native `inclusion: fileMatch` and `inclusion: manual` front-matter — it auto-scopes
  rules without needing nested files. The steering files are richer and Kiro-specific.
- Codex loads nested `AGENTS.md` files automatically when it enters a subtree — this is its
  native scoping mechanism. The nested files are the Codex-idiomatic equivalent.
- OpenCode reads `AGENTS.md` at root and traverses up from the current directory — it picks up
  nested files naturally. `opencode.json` only needs to reference the root `AGENTS.md`.
- Skills (`skill-*.md`) are **on-demand only** — never loaded always-on. Reference them in chat
  when the work type matches. Do not add them to `opencode.json` instructions.

---

## File Map

### Always-On (loads in every session)

| File | Purpose |
|---|---|
| `platform-base.md` | Repo identity, layer ownership, workload contract, metadata ownership, delivery shape, quality gates |

### Scoped (loads automatically when matching files are open)

| File | Activates when working in |
|---|---|
| `domain-and-application-packages.md` | `packages/**/*.py` |
| `workload-apps.md` | `apps/**/*.py` |
| `infrastructure-terraform.md` | `infra/**/*.tf` |
| `github-actions-workflows.md` | `.github/workflows/*.yml` |
| `data-and-schema.md` | `db/`, `packages/infrastructure/`, `tests/data/`, `scripts/data/` |
| `tests.md` | `tests/**/*.py` |

### On-Demand Skills (load manually for specific work types)

Invoke these by referencing them in chat with `#skill-<name>` when the work type matches.

| File | Load when |
|---|---|
| `skill-clean-architecture.md` | Adding, changing, or refactoring code across the `packages/` / `apps/` boundary |
| `skill-ddd.md` | Modeling new domain concepts, adding aggregates, designing domain events |
| `skill-release-it.md` | Working on services, APIs, health checks, Dapr integrations, or production reliability |
| `skill-ddia.md` | Schema changes, outbox pattern, event consumers, data export, backfill, idempotency |
| `skill-pragmatic-programmer.md` | General engineering work, automation, technical debt, code quality |
| `skill-refactoring.md` | Refactoring passes, module boundary improvements, cleaning up smells |

---

## Design Principles

**One always-on base, scoped additions, on-demand skills.**

- The base file (`platform-base.md`) is always loaded and covers the non-negotiable platform rules.
- Scoped files add layer-specific rules only when the relevant files are in context — they do not pollute sessions focused on unrelated layers.
- Skills are loaded on-demand for specific work types. They bring in the relevant engineering book's decision rules, trigger rules, and final checklist, adapted to this repo's context.

**No conflicting rule sets loaded simultaneously.**

The compatibility matrix from agent-rules-books was used to select a non-conflicting combination:
- Clean Architecture + DDD (IDDD/Distilled) + DDIA + Release It! + Pragmatic Programmer + Refactoring/APoSD are all ✅ complementary.
- PoEAA was excluded because it conflicts with DDD (❌).
- Only one DDD variant is loaded at a time (IDDD + Distilled combined into `skill-ddd.md`).

**Rules are grounded in this repo's actual contracts.**

Every rule references real paths, real tools, and real conventions from this repo.
Generic book rules that don't apply here were omitted.

---

## Updating These Rules

- Update `platform-base.md` when the platform contract changes (new workload class, new delivery gate, new metadata ownership rule).
- Update scoped files when layer conventions change.
- Update skill files when the engineering standards for a work type evolve.
- Do not add a new always-on file without a strong reason — keep the always-on surface small.
