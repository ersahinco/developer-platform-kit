# Platform Concerns

`platform/concerns/` is the repository home for shared runtime capabilities.

- `dapr/`: Dapr components, config, resiliency, and environment profiles
- `observability/`: local-first Grafana, Loki, Prometheus, Promtail, and Tempo
- `security/`: reserved for shared runtime security concerns
- `policy/`: reserved for policy-as-code or policy guidance when real rules exist
- `networking/`: reserved for shared runtime networking concerns

Keep these concerns declarative. They should describe platform capabilities and
environment profiles, not become a custom orchestration layer.

Current profile rule:

- `local` profiles own Compose-friendly and OSS-local implementations
- `aws` or production-facing profiles own the current ECS/RDS/AWS runtime shape

When a concern differs by environment, prefer making that difference explicit
in the concern itself instead of scattering it across scripts and workflow
defaults.
