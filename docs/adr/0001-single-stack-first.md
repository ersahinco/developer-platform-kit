# ADR 0001: Single Stack First

## Status

Accepted

## Context

The project currently demonstrates a complete ECS delivery path with one VPC,
one ECS cluster, one app service, one PostgreSQL database, and one Terraform
state. The main learning artifact is safe in-place rollout, not environment
promotion.

## Decision

Keep the current single-stack model until there is a concrete lifecycle reason
to split Terraform into multiple stacks or environments.

## Consequences

- The repo stays easier to understand and operate.
- Safe rollout remains focused on migrations, runtime switches, ECS deploys, and one-off tasks.
- Future multi-stack work must justify the added state, naming, workflow, and documentation overhead.
