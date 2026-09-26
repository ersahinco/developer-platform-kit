# __PIPELINE_NAME__

Spark pipeline and the schema it depends on, owned by __OWNER__. Scaffolded from
the developer platform kit `data` template.

```text
pipeline/main.py     extract, transform, check, load
pipeline/checks.py   the check engine
checks.json          the checks themselves, reviewed in diffs
migrations/          Liquibase changelog and its image
tests/               check-engine tests, no Spark needed
```

## First

```bash
uv sync
uv run pytest -v
```

## Order of stages

`extract → transform → check → load`. Checks run **before** the load. A pipeline
that publishes first and reports a violation afterwards has already spread it
downstream.

## Checks

Declared in `checks.json`, evaluated by `pipeline/checks.py`. Kinds:
`row_count_min`, `null_rate_max`, `unique`, `freshness_max_hours`,
`accepted_values`.

| Result | Means | Fix |
|---|---|---|
| `passed` | The rule held | Nothing |
| `failed` | The check ran, the data violated it | The data, or the threshold if it was wrong |
| `errored` | The check could not run: missing column, missing dataset | The check or the pipeline. The data may be fine |

`blocking: true` stops the run. `blocking: false` records a warning and
continues. Any `errored` stops the run, because an unevaluated check proves
nothing.

The job writes `checks.json` to S3 and the lane prints it as a table in the run
summary.

## Exit codes

| Code | Means |
|---|---|
| 0 | Checks allowed the load, and the load finished |
| 1 | A blocking check failed, a check errored, or the transform broke |
| 2 | `checks.json` is invalid. No data was read, so a rerun with the same file fails identically |

## Schema changes

Every change goes through phases, one pull request and one apply each:

| Phase | Change | Deployed code |
|---|---|---|
| Expand | Add nullable columns, tables, indexes | Untouched, still works |
| Dual write | Nothing | Writes both shapes |
| Backfill | Nothing | Fills the new shape for old rows |
| Switch | Nothing | Reads the new shape only |
| Contract | Drop the old columns | Nothing reads the old shape |

Skipping expand creates a window where the running code and the schema disagree.
Changesets are append-only and each carries a rollback.

## Delivery

`.github/workflows/data.yml`.

| Trigger | Does |
|---|---|
| Pull request | Lint, check-engine tests, apply the changelog to a throwaway Postgres, prove one rollback |
| Push to main | Publishes the migration image |
| Manual, mode `migrate` | Runs the selected `image_tag` as an ECS task. `rollbackCount` rolls back exactly one changeset. Run `updateSQL` and read it before `update` |
| Manual, mode `pipeline` | Publishes the job code under the commit SHA and runs it on EMR Serverless |

Both manual modes need `confirm: run`. The pipeline defaults to `dry_run: true`,
which runs every stage except the load.

## Repository settings

- repository secret `AWS_ROLE_ARN`; an `aws` environment with required reviewers and protected deployment branches
- variables `ECS_CLUSTER`, `PRIVATE_SUBNET_IDS`, `MIGRATION_SECURITY_GROUP_IDS`, `EMR_APPLICATION_ID`, `DATA_CODE_BUCKET`
- repository secret `EMR_JOB_ROLE_ARN` for the Spark execution role

All of them are outputs of the infra repo.

Use a new, run-specific target prefix for each Spark publication. Existing targets
are rejected; promoting or replacing a published dataset is a separate consumer
decision. Install `uv sync --extra spark` for local Spark execution with Java 17.
The starter uses Spark 3.5.2 to match [EMR 7.5.0](https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/release-version-750.html).
