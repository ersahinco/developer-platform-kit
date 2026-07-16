# AWS Catalog

This is the home for reusable AWS building blocks as they are extracted from
the current assembly roots.

It is the current runtime-target catalog root. Future runtime targets should
follow the same pattern under `infra/catalog/<runtime-target>/`.

Current catalog areas:

- network baseline
- ECS service/task baseline
- RDS baseline
- Dapr broker backing resources
- object storage baseline
- app delivery identity baseline
- bounded external dependency review patterns

Keep implementation in `infra/platform` and `infra/app` until a reusable
boundary is concrete enough to prove. An incubating catalog entry may precede
broad adoption when it has an owner, contract input, implementation reference,
and evidence path. It must not become a second workload contract.
