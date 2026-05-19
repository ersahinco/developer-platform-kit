# Observability Concern

This concern owns the portable, local-first observability surface:

- Prometheus-compatible metrics
- Loki-compatible logs
- Tempo-compatible OTLP traces
- Grafana dashboards and datasource provisioning

Environment profiles:

- `local`: Prometheus, Loki, Tempo, Grafana, and Promtail assets consumed by
  `compose.yaml`
- `aws`: CloudWatch logs, CloudWatch alarms, and optional ADOT sidecar wiring
  owned through `infra/app` and observability scripts

Alarm ownership stays explicit:

- workload-facing app metrics remain Prometheus-shaped
- release and incident evidence can snapshot platform-owned AWS alarms
- AWS managed-resource alarms remain platform-owned, not workload-declared
- workload-derived alarm names should come from the platform/workload contract,
  not handwritten script inventories

CloudWatch remains the AWS-native signal plane for rollback and managed
resource alarms. Do not reintroduce hosted LGTM services into Terraform unless
they become a deliberate platform module.
