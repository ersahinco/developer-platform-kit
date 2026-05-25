# Platform Terraform Root

`infra/platform/` owns bootstrap resources with an app-independent lifecycle for
the current AWS runtime:

- VPC, subnets, NAT, service endpoints
- GitHub Actions OIDC identity, Terraform state access, CI IAM policies
- account and domain lookups used by app-owned DNS

It does not own RDS, ECS, ALB/API edge, queues, data buckets, jobs, logs, or
ADOT wiring.

This root is a runtime realization layer, not part of the stable center.
