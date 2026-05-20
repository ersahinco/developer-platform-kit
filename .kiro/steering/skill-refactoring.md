---
inclusion: manual
---

# Skill: Refactoring

Load for refactoring passes, module-boundary cleanup, or when code feels harder
to change than it should.

## Core Rule

Refactoring is behavior-preserving. Simplicity means lower cognitive load, not
more files or more names.

## Rules

- Refactor in small safe steps; keep tests passing.
- Keep refactoring commits separate from feature or bug-fix commits.
- Add characterization tests first when behavior is unprotected.
- Diagnose the smell before choosing the refactor.
- Prefer deep modules over pass-through wrappers.
- Hide volatile details and internal representations behind small semantic
  interfaces.
- Combine or split modules by total complexity, not size or habit.

## Common Smells

- long method or large class
- feature envy
- data clumps
- primitive obsession
- divergent change
- shotgun surgery
- inappropriate intimacy across boundaries

## Repo Rules

- preserve dependency direction in `packages/`
- new modules must hide more complexity than they add
- rename toward `docs/ubiquitous-language.md`
- verify complexity was removed, not pushed to the caller

## Checklist

- observable behavior unchanged
- tests pass before and after
- dependency direction preserved
- names match the ubiquitous language
- new boundaries hide more complexity than they add
