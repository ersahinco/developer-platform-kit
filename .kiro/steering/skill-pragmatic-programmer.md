---
inclusion: manual
---

# Skill: The Pragmatic Programmer (Hunt & Thomas)

Load this when: doing general engineering work, refactoring, adding automation, reviewing code quality, or when something feels like it's accumulating technical debt.

This is the general-purpose engineering operating style for this repo.

---

## Primary Bias to Correct

Do not optimize only for the local edit or the requested feature. Own the outcome by reducing duplicated knowledge, keeping concerns independent, proving assumptions early, automating repeated work, and making intent clear.

---

## Decision Rules

- Keep one authoritative representation for each piece of system knowledge. Business rules, validation, status semantics, config meaning, and workload metadata should derive from or trace to one owner. In this repo: `platform/workloads.json` is the single source of truth for workload identity — do not duplicate it in Terraform, workflows, or scripts.
- Preserve orthogonality: keep components independent, responsibilities non-overlapping, interfaces narrow. The layer boundaries (`domain` / `application` / `infrastructure` / `apps`) are the orthogonality contract — respect them.
- Keep volatile decisions reversible where practical. Do not hard-code AWS resource names, ECS cluster names, or deployment environment details into application code.
- Automate repetitive, error-prone, or ritualized work. `make lint`, `make secret-scan`, `make runtime-conformance`, and the CI gates exist for this reason — do not bypass them.
- Shorten feedback loops. Add tests, automated checks, and visible failures before late expensive surprises.
- Make contracts, assumptions, invariants, and responsibilities explicit and close to the abstraction they protect.
- Apply the broken windows rule: fix or visibly contain small quality decay before bad code, unclear ownership, or broken process becomes normal.
- Think beyond the local edit: quick fixes that multiply future maintenance cost are usually a bad bargain; leave touched areas better where the cost is low.

## Applied to This Repo

- **DRY at the knowledge level**: If a workload name, port number, or config key appears in more than one place, one of those places should derive from `platform/workloads.json`.
- **Automation**: If you find yourself running the same manual step more than twice, it belongs in `scripts/` or a `Makefile` target.
- **Tracer bullets**: When adding a new workload, get the full slice working end-to-end (contract declared → image builds → health check passes → runtime conformance passes) before adding complexity.
- **Broken windows**: If you touch a file and notice a naming inconsistency, a missing test, or a violated layer boundary, fix it if cheap or leave an explicit TODO with a ticket reference.

## Trigger Rules

- When the same fact appears in multiple artifacts, choose one owner and derive or validate the rest.
- When one change requires edits in many unrelated places, repair the missing boundary or hidden coupling.
- When volatile details are hard-coded, move them into validated, controlled configuration or metadata.
- When repeated manual steps appear in runbooks or operator docs, automate and version them.
- When tests are slow, flaky, or require excessive unrelated setup, improve the feedback path.
- When local decay appears in touched code, fix it if cheap or leave an explicit containment path.

## Final Checklist

- [ ] One authoritative owner for each system fact — no duplication of workload metadata?
- [ ] Unrelated concerns independent and volatile choices reversible?
- [ ] Repeatable work automated, versioned, and aligned with shared checks?
- [ ] Tests automatic, relevant, and run before calling the change done?
- [ ] Touched area better or explicitly contained?
- [ ] Names, comments, and commits communicate intent?
