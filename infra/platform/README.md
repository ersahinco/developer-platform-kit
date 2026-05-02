# Platform Terraform Root

This root is the Session 5 platform/bootstrap side of the split. It owns
AWS-bound resources with a lifecycle independent of the app workload:

- VPC, subnet tiers, NAT, and AWS service endpoints.
- GitHub Actions OIDC role identity, Terraform state access, and CI IAM policies.
- Account/domain lookups used by app-owned DNS records.

It intentionally does not own RDS, ECS compute, ALB/API edge, workload queues,
data buckets, jobs, or Grafana/Loki/Prometheus observability. Those belong in
the app root.
