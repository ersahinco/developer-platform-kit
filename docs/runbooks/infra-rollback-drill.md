# Infra Rollback Drill

Use this drill to practice infrastructure rollback without changing application
data, database schema, data hub objects, or runtime order data.

The drill uses the existing Terraform path:

```text
infra-only change
  -> Infra Plan
  -> Infra Apply
  -> observe
  -> revert commit
  -> Infra Plan
  -> Infra Apply
  -> verify restored state
```

## Good Drill Targets

Use reversible, no-data infrastructure or observability changes:

| Target | Good for | Avoid |
|---|---|---|
| Grafana dashboard JSON | Practicing config rollout and rollback. | Dashboard changes that hide all rollback signals. |
| Prometheus alert threshold or label | Practicing Grafana-stack alert rollback. | Removing every app health alert at once. |
| CloudWatch app symptom alarm threshold | Practicing AWS-native alarm rollback while dual-running Grafana. | RDS, S3, or queue deletion/replacement. |
| ECS desired count for non-production drill windows | Practicing Terraform-controlled compute rollback. | Running during active investigation or load tests. |

Do not use schema changes, bucket lifecycle changes, RDS changes, SQS queue
replacement, object deletion, or runtime `READ_MODE`/`WRITE_MODE` changes for a
no-data rollback drill.

## Forward Change

1. Create a normal pull request with one small infra or observability change.
2. Wait for `Infra Plan`.
3. Review that the plan contains no database, S3 object, queue replacement, or
   destructive change.
4. Merge to the default branch.
5. Run `Infra Apply` with the reviewed plan run id.

After apply, verify only the changed surface. Examples:

```bash
make grafana-tunnel
```

```bash
make observability-delivery-verify
```

## Rollback Change

Revert the forward commit rather than editing by hand:

```bash
git revert <forward-commit-sha>
```

Open the revert pull request and repeat the same reviewed plan/apply path:

```text
revert PR
  -> Infra Plan
  -> review no-data plan
  -> merge
  -> Infra Apply
```

## Verification

After rollback:

- Grafana dashboard or alert state matches the previous version.
- `make observability-delivery-verify` still passes.
- No data hub objects were created or deleted by the drill.
- No Liquibase, backfill, data-export, or runtime mode workflow was run.

## Stop Conditions

Stop the drill and do not apply if the plan includes:

- RDS replacement or modification unrelated to the drill.
- S3 bucket deletion, lifecycle tightening, or object deletion.
- SQS/SNS replacement.
- ECS task or service replacement outside the intended target.
- Any Liquibase, data export, or backfill action.
