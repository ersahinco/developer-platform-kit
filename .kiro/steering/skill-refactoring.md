---
inclusion: manual
---

# Skill: Refactoring (Martin Fowler) + A Philosophy of Software Design (Ousterhout)

Load this when: doing a refactoring pass, cleaning up technical debt, improving module boundaries, or when code feels awkward to change.

---

## Primary Bias to Correct

Working code, small pieces, familiar patterns, and extra documentation do not make a design simple when they increase cognitive load or leak knowledge. Refactoring is behavior-preserving — keep it separate from feature changes.

---

## Refactoring Rules (Fowler)

- Refactor in small, safe steps. Each step must leave the tests passing.
- Keep refactoring commits separate from feature or bug-fix commits — do not mix behavior changes with structural changes.
- Before refactoring, ensure the code under change has tests that protect its observable behavior. If tests are missing, add characterization tests first.
- Use code smells as diagnostic signals, not as automatic refactoring triggers. Diagnose before treating.
- Common smells in this codebase to watch for:
  - **Long method / large class**: extract to use case, domain service, or value object
  - **Feature envy**: a method in `apps/` or `packages/infrastructure/` that does domain work — move it inward
  - **Data clumps**: repeated groups of parameters that should be a value object
  - **Primitive obsession**: raw strings/ints for domain concepts — promote to value objects
  - **Divergent change**: one class changes for multiple unrelated reasons — split by responsibility
  - **Shotgun surgery**: one change requires edits in many places — consolidate the knowledge
  - **Inappropriate intimacy**: `apps/` code reaching into `packages/domain/` internals — restore the boundary

## Module Design Rules (Ousterhout)

- Prefer deep modules: small, semantic interfaces that hide meaningful internal complexity.
- Reject pass-through services, thin wrappers, and tiny split-outs that add names without reducing reader burden.
- Design interfaces around what callers need to know, not how the implementation works.
- Hide volatile decisions, internal representations, storage shape, and messy edge handling inside the module that owns the knowledge.
- Pull complexity downward when the lower module owns the detail.
- Combine or split by total complexity, not by size or habit.

## Applied to This Repo

- When refactoring `packages/`: verify the dependency direction is preserved after the refactor
- When extracting a new module: prove it hides more complexity than it adds
- When renaming: use the ubiquitous language from `docs/ubiquitous-language.md` as the target vocabulary
- When simplifying a use case: check whether the complexity moved to the caller or was genuinely eliminated

## Trigger Rules

- When a feature feels awkward or one change spreads across files, look for missing information hiding, shallow modules, or complexity pushed to callers.
- When adding a module, layer, helper, or wrapper, prove that it hides more complexity than it adds.
- When splitting or extracting, check whether the new boundary captures meaning or only adds jumps and pass-through state.
- When naming is vague, mechanism-focused, or inconsistent, reconsider the abstraction boundary.

## Final Checklist

- [ ] Refactoring commits are separate from feature/fix commits?
- [ ] Tests pass before and after each refactoring step?
- [ ] Observable behavior is unchanged?
- [ ] Dependency direction preserved — no new inward-to-outward imports introduced?
- [ ] Names match the ubiquitous language?
- [ ] New boundaries hide more complexity than they add?
- [ ] Code smells diagnosed and treated, not just moved?
