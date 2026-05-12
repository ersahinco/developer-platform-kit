# Config And Secrets Contract

Configuration should be boring, explicit, and portable. Application behavior is
controlled by env vars, mounted config, runtime config tables, or application
ports. Secret values are injected by the runtime secret mechanism and never
become part of images, logs, release artifacts, or plaintext Terraform values.

## Naming Rules

| Type | Rule |
| --- | --- |
| Env vars | Upper snake case, declared in `platform/workloads.json`, and named for application intent. |
| Secrets | Declared separately from env vars in `platform/workloads.json`; a name cannot be both config and secret. |
| Provider resources | Bucket, queue, task definition, IAM, and managed-service names stay at platform/delivery edges. |
| Runtime config | Operator-toggled behavior such as `READ_MODE` and `WRITE_MODE` belongs in the runtime config store. |
| Job controls | Batch size, sleep interval, max batches, run ID, and dates are explicit env vars. |

## Source By Environment

| Environment | Source |
| --- | --- |
| Local | `.env`, Docker Compose env, local Postgres/PgBouncer, LocalStack for Dapr broker tests, and test overrides. |
| CI | GitHub Actions env and service containers for non-secret test values. |
| AWS runtime | ECS env, Secrets Manager injection, runtime config table, and Terraform-owned resource names. |
| Future runtime | Equivalent env/config/secret injection that satisfies the same workload contract. |

## Guardrails

- Prefer full URLs for local and test ergonomics.
- Allow composed `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`, and injected
  `DB_PASSWORD` for runtimes that should not store full URLs in deployment
  config.
- Do not log secret values or generated URLs containing secret values.
- Do not add provider-specific config to `packages/domain` or
  `packages/application`.
- Update `platform/workloads.json` and run
  `scripts/ci/validate_platform_contract.py` when config changes.
