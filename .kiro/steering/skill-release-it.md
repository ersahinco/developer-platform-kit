---
inclusion: manual
---

# Skill: Release It!

Load when working on services, APIs, jobs, Dapr integrations, deployment
paths, health checks, or other production-critical paths.

## Core Rule

A passing happy path is not production readiness. Design failure semantics,
limits, recovery, and diagnosis early.

## Rules

- Assume dependencies, queues, timeouts, and degraded states fail in slow,
  partial, or prolonged ways.
- Put explicit time limits on outbound calls.
- Retry only when safe; bound count and total time.
- Isolate dependency failures with circuit breakers, bulkheads, or separate
  pools where appropriate.
- Design overload behavior explicitly.
- Release scarce resources deterministically.
- Validate external input and responses before trusting them.
- Build observability into boundaries and failure points.
- Make startup, health checks, migrations, and jobs safe, observable, and
  restartable.

## Repo Rules

- `/ready` reflects real dependency reachability
- Dapr retry and dead-letter behavior belongs in `platform/concerns/dapr/`
- outbox relay failures stay bounded and observable
- jobs emit structured failure events and exit non-zero on failure
- long-running services use PgBouncer and avoid holding transactions across slow calls
- CloudWatch alarms protect observable workload behavior

## Triggers

- adding an outbound call, Dapr publish, S3 operation, or query
- adding a queue, buffer, or background job
- touching deployment, startup, migrations, or operational automation
- adding health checks or load balancing
- reviewing an incident or performance failure

## Checklist

- explicit timeouts
- safe bounded retries
- bounded queues, pools, and payloads
- failure isolation where needed
- diagnostics for logs, metrics, health, correlation, and dependency state
- restartable startup, deployment, migration, and jobs
