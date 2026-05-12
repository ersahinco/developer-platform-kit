# Database Portability Contract

This project depends on PostgreSQL semantics, not on RDS as an application
contract. RDS is the current AWS runtime implementation. A future runtime could
use Supabase, Neon, Cloud SQL for PostgreSQL, Azure Database for PostgreSQL, or
another managed PostgreSQL service if it satisfies this contract without app
code changes.

## Application Contract

Workloads should see the database through portable PostgreSQL connection
configuration:

| Area | Contract |
| --- | --- |
| Engine | PostgreSQL-compatible SQL, transactions, constraints, indexes, and advisory migration locking used by Liquibase. |
| Connection strings | Services accept `DATABASE_URL`; jobs accept their job-specific URL such as `BACKFILL_DATABASE_URL` or `DATA_EXPORT_DATABASE_URL`. |
| Composed config | Runtimes may provide `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`, and injected `DB_PASSWORD` instead of a full URL. |
| Secrets | `DB_PASSWORD` is injected by the runtime secret mechanism and is not committed, logged, stored in images, or stored in plaintext Terraform variables. |
| Pooling | Request-serving services use PgBouncer transaction pooling. Long-running jobs and Liquibase connect directly to PostgreSQL. |
| Migrations | Liquibase owns DDL, migration history, and migration locks. App containers do not apply schema changes at startup. |
| Readiness | `/ready` checks database availability for long-running workloads and reports `database` as a structured readiness check. |
| Rollback | Schema rollback stays forward-compatible until contract. After destructive contract changes, recovery is database restore or forward fix, not app image rollback. |

`packages/domain` and `packages/application` must not import SQLAlchemy,
PostgreSQL drivers, provider SDKs, or provider-specific database APIs.
Database implementation details belong in `packages/infrastructure/db`,
`db/`, runtime app settings, and platform/delivery edges.

## Current AWS Implementation

The current runtime uses RDS PostgreSQL, AWS Secrets Manager, ECS task
definition secret injection, PgBouncer, and CloudWatch RDS alarms. Those are
implementation choices at the AWS platform edge.

CloudWatch is acceptable for RDS CPU, storage, and connection pressure because
those are provider-managed infrastructure signals. CloudWatch must not become
the application observability contract. App-level database symptoms still show
up through readiness, Prometheus metrics, Loki logs, Tempo traces when enabled,
and release evidence.

## Future Provider Requirements

Before replacing or adding a database provider, prove:

- The provider is PostgreSQL-compatible for the SQL, transaction, migration,
  and locking behavior used here.
- Liquibase can run as a one-off job against the target database.
- Request workloads can use PgBouncer or an equivalent transaction-pooling
  strategy without changing app code.
- Long-running jobs can connect directly when transaction pooling is the wrong
  fit.
- Credentials are injected by the runtime secret mechanism.
- Backup, restore, point-in-time recovery or snapshot behavior, and destructive
  migration recovery are documented.
- Provider-native metrics remain at the platform edge, while app telemetry
  keeps the Prometheus/Loki/Tempo/Grafana baseline.
- Terraform ownership is explicit: bootstrap/platform networking and
  app/runtime database ownership do not blur.

Do not add a second database provider only to prove portability. Add one when a
real workload benefits from a different managed PostgreSQL implementation.
