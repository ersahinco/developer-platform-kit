# developer-platform-kit - Agent Rules

`CLAUDE.md` imports this file. `README.md` is the only prose doc; keep it that
way.

This repo is scaffolding and shared delivery. It is not an application and not a
framework.

## Layout

| Path | Owns | Must not own |
|---|---|---|
| `repo-templates/<name>/template.json` | The variables a template needs | Values, environments, account IDs |
| `repo-templates/<name>/files/` | The tree rendered into a new repo | Anything only this repo needs |
| `.github/workflows/reusable-*.yml` | One lane per team, called by ref | Stack names, regions, cluster names |
| `.github/workflows/ci.yml` | This repo's gates | Anything touching a cloud account |
| `modules/aws/<name>/` | One capability | Stack wiring, workload identity |
| `scaffold/` | Rendering | Template content |
| `tests/` | Proving templates render and lanes hold their shape | Production code |

## Hard rules

- Three templates, three lanes: app, infra, data. A fourth needs a fourth audience, and a test enforces the count.
- A template that does not render is broken. `make test` is the gate.
- Tokens are `__UPPER_SNAKE__`, declared in `template.json`. An undeclared token fails the render and names the file.
- Derived values are computed, never declared. Any `*_NAME` yields `*_SLUG`.
- Each lane is one file with a `mode`, one job per mode, gated by `if: inputs.mode == '...'`. Two modes never run in the same run.
- Build never deploys. Plan never applies. Apply checks the plan run succeeded, ran on the default branch, and planned current head.
- Immutable tags only. `latest` is rejected by the lane, not by a reviewer.
- Credentials arrive through `secrets:`, never `inputs:`.
- Third-party actions pinned to a full SHA, version in a trailing comment.
- Every cloud-changing mode writes `release-event.json` and takes a literal `confirm` where the change is not reversible.
- Evidence is written inline with `jq`. A consumer must not need a script from this repo.
- Modules take `name` and `tags`. Resource names derive from `name`.
- A module with no caller in a template gets deleted.
- Enforce what costs money or data with `validation` and `precondition`. Explain the rest in a comment.

## Error messages

Two failures, two messages. A task that ran and exited non-zero, a task that
never started, and a rollout still in progress are three situations with three
next steps. A check that failed and a check that could not run are not the same
either. Say which happened.

## Adding a template or module

Nothing new to write in the test suite: it is generic over templates and modules.
A template needs `template.json` with a description, example, and pattern per
variable, plus the tree in `files/`. A module needs `main.tf`, `variables.tf`,
`outputs.tf`, `versions.tf`, a description on every variable and output, and a
caller in a template.

```bash
make check
make validate-modules lint-tflint lint-checkov
```

## Not here

- An application, domain model, or schema of our own
- A control plane, portal, or catalog server
- Provider-neutral module wrappers
- A second runtime target with no consumer
- A docs tree. One README, plus the README each template renders
