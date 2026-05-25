# App Terraform Root

`infra/app/` owns the current AWS runtime resources:

- database persistence and security groups
- ECS cluster, services, support tasks, ECR
- ALB/API edge, certificate, app DNS
- object storage, schedules, messaging, app IAM
- app alarms, logs, optional ADOT sidecar

It consumes `infra/platform` outputs through remote state.

This root is a runtime realization layer, not part of the stable center. Keep
workload meaning in `platform/workloads.json` and shared capability intent in
`platform/concerns/`.

Do not define VPC, subnets, Route 53 zone lookups, or GitHub OIDC identity
here. Check `../catalog/aws/extraction-map.md` before extracting a module.
