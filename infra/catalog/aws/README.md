# AWS Catalog

This is the home for reusable AWS building blocks as they are extracted from
the current assembly roots.

It is the current runtime-target catalog root. Future runtime targets should
follow the same pattern under `infra/catalog/<runtime-target>/`.

Expected candidates over time:

- network baseline
- ECS service/task baseline
- RDS baseline
- Dapr broker backing resources
- object storage baseline
- app delivery identity baseline
- bounded dependency baseline for identity, DNS, external APIs, external databases, and partner systems

Until real reuse exists, keep implementation in `infra/platform` and
`infra/app`.

See [extraction-map.md](extraction-map.md) for the current candidate list and
the rule for when a capability should move from assembly-root Terraform into
the AWS catalog.
