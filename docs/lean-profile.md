# Lean Profile

Use this profile when a change should make the toolkit smaller, clearer, or
less dependent without reducing the portable workload contract.

The rule is simple:

Keep code that encodes product/runtime truth. Delete code that only compensates for unclear ownership.

## What It Combines

This is not seven separate reviews. It is one small profile that takes the
useful parts of each discipline:

| Lens | Keep |
|---|---|
| Dependency audit | Direct and transitive runtime dependencies by image, optional extras, lock drift, known vulnerabilities. |
| Codebase health review | Dead paths, stale docs, duplicate scripts, confusing ownership, files too large to scan quickly. |
| Complexity budget | Net files, lines, workflows, Make targets, Terraform resources, and commands added per capability. |
| Architecture fitness function | Machine-checkable proof that the repo still behaves like a toolkit, not a private framework. |
| Maintainability review | One owner per concept, canonical docs, names from ubiquitous language, readable tests. |
| Supply-chain/risk review | Pinned images, secret scanning, SAST, dependency advisories, smallest required build/runtime tools. |
| Platform surface-area review | Public commands, workflows, runtime contracts, deployment paths, and observability entrypoints. |

## Fitness Questions

Ask these before adding or keeping code:

1. Does this encode a durable product or runtime fact?
2. Is this the canonical owner, or is it repeating another file?
3. Can a proven standard tool own this behavior instead?
4. Does a workload, operator, or platform maintainer actually call this path?
5. Does the dependency belong in every image, or only in a specific job or
   optional extra?
6. Does the code make ownership clearer, or does it compensate for unclear
   ownership?
7. Can the rule be expressed as schema, tests, or a small contract instead of
   prose scanning or bespoke orchestration?

Keep the path when the answer points to product/runtime truth. Delete, move, or
make optional when the answer points to ownership fog.

## Lean Commands

Run the narrowest set that answers the question. Widen only when the change
touches shared contracts or release paths.

```shell
git status --short
rg --files | wc -l
rg --files | xargs wc -l | sort -n | tail -30
rg --files | rg '(^docs/.*\.md$|^README\.md$)' | xargs wc -l | sort -n
rg -n "TODO|FIXME|deprecated|retired|legacy|temporary|workaround" README.md docs .github infra scripts tests
uv tree
uv lock --check
make dependency-audit
uv run python scripts/ci/validate_platform_contract.py
make lint-docs
```

Use existing repo checks as the architecture fitness function:

```shell
uv run pytest tests/contracts -q
uv run ruff check apps/ packages/ tests/ scripts/
uv run pyright
```

Use runtime conformance when a change touches workload shape, container
behavior, ports, health checks, or platform runtime expectations:

```shell
make runtime-conformance
```

## Budget Signals

Treat these as prompts for review, not hard quotas:

| Signal | Review When |
|---|---|
| New runtime dependency | It is inherited by more than one image or duplicates a standard platform capability. |
| New workflow job | It repeats build, deploy, scan, or evidence logic already driven by metadata. |
| New Make target | It is an alias for a command with no ownership or operator value. |
| New Terraform resource group | It hand-wires a standard service that a module, sidecar, or managed service can own. |
| New top-level doc | It overlaps an existing canonical doc or restates project state. |
| New contract test | It protects machine-readable ownership, runtime behavior, or repo shape instead of exact prose. |
| Script over 200 lines | It orchestrates a tool that already has a CLI, module, or workflow primitive. |
| Doc over 300 lines | It mixes terms, current state, runbook actions, and architecture rationale. |

## Output

Record the review in the smallest useful form:

```text
Lean profile:
- Kept:
- Removed or made optional:
- Dependency change:
- Surface change:
- Ownership decision:
- Validation:
```

Prefer a commit that removes ambiguity and proves the remaining path. A good
result is not just fewer lines; it is fewer places a human or coding agent must
inspect to understand the same capability.
