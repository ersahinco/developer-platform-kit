# Platform Terraform Root

This root owns AWS-bound platform/bootstrap resources with a lifecycle
independent of the app workload:

- VPC, subnet tiers, NAT, and AWS service endpoints.
- GitHub Actions OIDC role identity, Terraform state access, and CI IAM policies.
- Account/domain lookups used by app-owned DNS records.

It intentionally does not own RDS, ECS compute, ALB/API edge, workload queues,
data buckets, jobs, ALB access logs, or ADOT sidecar wiring. Those belong in the
app root.
