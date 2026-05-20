---
inclusion: manual
---

# Skill: Release It! (Michael T. Nygard)

Load this when: working on services, APIs, job workloads, Dapr integrations, deployment paths, health checks, or any code on a critical production path that must survive failures, overload, or operational mistakes.

---

## Primary Bias to Correct

A passing happy path is not production readiness. Design the failure semantics, demand limits, isolation, recovery path, and diagnosis surface before production defines them for you.

---

## Decision Rules

- Assume every dependency, queue, timeout, and degraded state can fail in slow, partial, or prolonged ways.
- Put explicit, intentional time limits on all outbound calls. Do not rely on library defaults or allow infinite waits.
- Retry only when the operation is safe for the caller and provider; bound count and total time, use backoff or jitter, do not retry validation errors or permanent failures.
- Isolate dependency failures with circuit breakers, bulkheads, and separate resource pools so one outage cannot consume all threads or connections.
- Design overload behavior explicitly: back pressure, finite queues, load shedding of lower-value work before core functions collapse.
- Budget scarce resources explicitly — release them deterministically. Avoid holding connections across slow remote calls.
- Treat external input and external responses as untrusted: validate syntax, shape, business plausibility, and semantics before trusting them.
- Build observability into boundaries and failure points: structured context, correlation identifiers, latency, throughput, error, saturation, queue depth, retry counts, and breaker state.
- Make startup, health checks, migrations, and one-time jobs fail safely, observable, stoppable, and recoverable.

## Applied to This Repo

- **`/health` and `/ready`**: `/ready` must reflect real dependency reachability — not just process liveness. A workload that cannot reach the database must return non-200 from `/ready`.
- **Dapr pub/sub**: Define retry, dead-letter, and resiliency semantics in `platform/concerns/dapr/` — do not leave them as Dapr defaults.
- **Outbox relay**: The relay process must handle Dapr publish failures gracefully — bounded retries, dead-letter path, structured failure events.
- **Job workloads**: Jobs must emit structured failure events and exit with a non-zero status on failure. Rerun safety must be documented.
- **Database connections**: Use PgBouncer for long-running services. Do not hold transactions open across slow external calls.
- **CloudWatch alarms**: Alarms protect observable workload behavior. Define them before deploying to production, not after the first incident.

## Trigger Rules

- When adding an outbound call, Dapr publish, S3 operation, or database query: define timeout, retry eligibility, retry bounds, fallback, and caller-survival behavior.
- When adding a queue, buffer, or background job: define capacity, full behavior, cleanup, and saturation monitoring.
- When a change touches deployment, startup, migrations, or operational automation: make it idempotent or restartable where practical.
- When adding health checks or load balancing: ensure traffic reaches only ready components.
- When reviewing an incident or performance failure: identify the failure chain, missing defenses, detection gaps, and design changes needed.

## Final Checklist

- [ ] Explicit timeouts — no infinite waits on outbound calls or Dapr operations?
- [ ] Retries safe, bounded, backed off, and not duplicated across layers?
- [ ] Queues, pools, and payloads bounded?
- [ ] Failure isolated — breakers, bulkheads, or fast failure where appropriate?
- [ ] External input validated before affecting state, caches, or downstream systems?
- [ ] Diagnostics cover logs, metrics, health, correlation, retry counts, and dependency state?
- [ ] Startup, deployment, migration, and job automation restartable and observable?
- [ ] `/ready` reflects real dependency reachability, not just process liveness?
