# ADR 0003: Prometheus, Loki, and Grafana Observability Target

## Status

Accepted

## Context

The project should be a credible DevOps and cloud platform demo. CloudWatch is
valuable on AWS, but the desired interview story also includes open-source
monitoring, logging, and dashboarding.

## Decision

Use Prometheus, Loki, and Grafana as the preferred observability target. Build
the first implementation locally, then decide whether to add an AWS-hosted
extension.

## Consequences

- The project can demonstrate portable observability concepts.
- CloudWatch remains documented as an AWS-native tradeoff.
- Observability is added as an optional extension so it does not complicate the base ECS rollout.
