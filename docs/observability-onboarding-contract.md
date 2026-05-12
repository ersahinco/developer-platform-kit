# Observability Onboarding Contract

Every new workload should be useful in the OSS observability stack before it is
treated as production-shaped. The app baseline is Prometheus, Loki, Tempo, and
Grafana. Provider-native metrics may still explain provider-managed
infrastructure at the platform edge.

## Workload Signals

| Signal | Contract |
| --- | --- |
| Metrics | Prometheus text for request count, request latency, readiness failures, errors, and workload-specific outcomes. |
| Logs | Loki-compatible structured logs with `stack`, `environment`, `service`, `container`, and workload correlation fields. |
| Traces | Optional OTLP/HTTP traces to Tempo when spans materially improve debugging. |
| Dashboards | Grafana panels use Prometheus, Loki, and Tempo as the app baseline. No CloudWatch datasource is required. |
| Evidence | Cloud-changing deploys, rollbacks, drills, and infra applies emit release events. |
| Incidents | Runbooks or evidence bundles include query hints for logs, metrics, traces, release events, and relevant job artifacts. |

## Minimum New Workload Checklist

- Add metrics names to `platform/workloads.json`.
- Add required log fields to `platform/workloads.json`.
- Decide whether traces are supported; use OTLP/HTTP if enabled.
- Make `/ready` expose dependency failure names for services.
- Add incident evidence query hints when the workload adds a new operator path.
- Update Grafana dashboards or document why existing dashboards cover the
  workload.

CloudWatch, Azure Monitor, Google Cloud Monitoring, or another provider-native
tool may be used for managed infrastructure signals. They should not become the
portable app observability contract.
