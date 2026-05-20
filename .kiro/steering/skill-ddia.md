---
inclusion: manual
---

# Skill: Designing Data-Intensive Applications (Martin Kleppmann)

Load this when: working on schema changes, the outbox pattern, event consumers, data export, backfill operations, idempotency, or any system where correctness depends on data ownership, consistency, or event flow.

---

## Primary Bias to Correct

Do not design distributed data behavior as if every write, read, queue, cache, and downstream side effect were local, ordered, fresh, and exactly once.

---

## Decision Rules

- Make core trade-offs explicit: source of truth, consistency expectation, retry behavior, duplicate and reordered work, partial failure, and data evolution.
- Treat crashes, partial writes, duplicate work, timeouts, stale reads, and unknown downstream success as normal inputs — not edge cases.
- Make commands, jobs, events, and stream processors safe under retry and replay with deduplication keys, naturally idempotent transitions, or an explicit transactional recovery contract.
- Separate commands, events, durable logs, and materialized views. Events describe facts; consumers must tolerate lag, duplicates, restart, replay, and versioned payloads.
- Design schemas, encodings, APIs, messages, and events as evolving contracts across old readers, old writers, old data, in-flight messages, and rolling upgrades.
- Match transactions and isolation to invariants. Make atomicity scope, commit behavior, and recovery semantics explicit.
- Treat indexes, caches, read models, and denormalized copies as derived data with explicit propagation, lag, observability, repair, and rebuild paths.
- Align service/workload boundaries with data ownership and update semantics. Do not casually split one tightly consistent business concept across workloads.

## Applied to This Repo

- **Outbox pattern**: The outbox write and the business state change must be in the same transaction. The relay process is the derived consumer — it must tolerate duplicate delivery and replay.
- **Backfill worker**: Backfill operations must be safe to rerun from any checkpoint in `backfill_progress`. Document the idempotency bound.
- **Schema migrations**: Follow the expand/contract pattern. Never make a breaking change in a single migration. Plan for old readers and old writers coexisting during rolling deploys.
- **Data export job**: Export outputs are derived data. The manifest record is the source of truth for export state. Exports must be rerunnable.
- **Event payloads**: Version event payloads. Old consumers must be able to read new events; new consumers must be able to read old events.
- **`order_event_receipts` and `idempotency_keys`**: These exist precisely because the system cannot assume exactly-once delivery. Use them.

## Trigger Rules

- When changing a write path: state the source of truth, consistency boundary, durability point, downstream effects, and behavior after timeout or unknown success.
- When adding or changing a cache, projection, or read model: define ownership, propagation, staleness, rebuild, and repair.
- When changing a schema, API, message, event, or payload meaning: plan compatibility for old readers, old writers, and old stored data.
- When adding retries, consumers, queues, or replayable batch work: prove duplicate, replay, ordering, and recovery safety.
- When choosing transaction isolation or weakening consistency: map each anomaly to the invariant it can break.

## Final Checklist

- [ ] Source of truth and derived representations are explicit?
- [ ] Consistency expectations, durability points, and conflict rules are concrete?
- [ ] Retries, duplicate delivery, replay, and unknown success are handled?
- [ ] Schemas, events, and messages evolve safely across mixed versions?
- [ ] Outbox write and business state change are in the same transaction?
- [ ] Backfill and export operations are rerunnable from a checkpoint?
- [ ] Idempotency keys used where natural idempotency is not possible?
- [ ] Lag, retries, failures, and repair paths are observable?
