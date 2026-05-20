---
inclusion: manual
---

# Skill: Designing Data-Intensive Applications

Load when working on schema changes, outbox flow, event consumers, exports,
backfill, idempotency, or data ownership.

## Core Rule

Do not design distributed data behavior as if writes, reads, queues, and side
effects were local, ordered, fresh, and exactly once.

## Rules

- Make source of truth, consistency expectation, retry behavior, duplicate
  handling, and data evolution explicit.
- Treat crashes, partial writes, duplicate work, stale reads, and unknown
  downstream success as normal inputs.
- Make commands, jobs, and consumers safe under retry and replay.
- Separate commands, events, durable logs, and materialized views.
- Design schemas, APIs, messages, and events for mixed-version rollout.
- Match transactions and isolation to invariants.
- Treat indexes, caches, and read models as derived data with rebuild and
  repair paths.

## Repo Rules

- outbox write and business state change stay in the same transaction
- backfill reruns safely from `backfill_progress`
- schema changes follow expand, dual-write, backfill, switch, contract
- export manifests are the source of truth for export state
- event payloads are versioned
- `order_event_receipts` and `idempotency_keys` exist for duplicate and replay
  safety

## Triggers

- changing a write path
- adding or changing a cache, projection, or read model
- changing schema, API, message, or event meaning
- adding retries, consumers, queues, or replayable batch work

## Checklist

- source of truth and derived representations are explicit
- retries, duplicates, replay, and unknown success are handled
- schemas and events evolve safely across mixed versions
- outbox and business write share one transaction
- backfill and export are rerunnable
