---
inclusion: manual
---

# Skill: The Pragmatic Programmer

Load for general engineering, refactoring, automation, and technical-debt
cleanup.

## Core Rule

Do not optimize only for the local edit. Reduce duplicated knowledge, shorten
feedback loops, and leave the touched area clearer.

## Rules

- Keep one owner for each system fact. In this repo,
  `platform/workloads.json` owns workload identity.
- Preserve orthogonality across `domain`, `application`, `infrastructure`, and
  `apps`.
- Keep volatile choices reversible. Do not hardcode runtime details in app
  code.
- Automate repeated manual work.
- Add tests and visible failures before late surprises.
- Make contracts, assumptions, and responsibilities explicit.
- Fix small quality decay when cheap, or leave an explicit containment path.

## Repo Heuristics

- repeated workload names, ports, or config keys should derive from
  `platform/workloads.json`
- repeated manual steps belong in `scripts/` or `Makefile`
- new workloads should work end to end before extra complexity is added

## Triggers

- the same fact appears in multiple artifacts
- one change requires edits in many unrelated places
- volatile details are hardcoded
- repeated manual steps appear in docs or runbooks
- tests are slow, flaky, or require unrelated setup

## Checklist

- one authoritative owner per system fact
- unrelated concerns stay independent
- repeatable work is automated and versioned
- tests run before the change is done
- touched area is better or explicitly contained
