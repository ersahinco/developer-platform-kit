# App Terraform Root

`infra/app/` owns runtime resources:

- database persistence and security groups
- ECS cluster, services, support tasks, ECR
- ALB/API edge, certificate, app DNS
- object storage, schedules, messaging, app IAM
- app alarms, logs, optional ADOT sidecar

It consumes `infra/platform` outputs through remote state.

Do not define VPC, subnets, Route 53 zone lookups, or GitHub OIDC identity
here. Check `../catalog/aws/extraction-map.md` before extracting a module.
