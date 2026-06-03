# Runtime Defaults

Opinionated runtime defaults for enterprise DevEx standardization.

The toolkit is intentionally opinionated, but the machinery lives at the
runtime and capability layer. Workloads declare needs and emit standard
evidence. Runtime targets choose the blessed implementation.

Machine-readable defaults live in `platform/runtime-defaults.json`.
Inspect active defaults with:

```bash
make runtime-defaults
```

## Active Runtime Targets

| Runtime target | Authn default | Identity default | Secrets default | Observability default |
|---|---|---|---|---|
| `local-compose` | `none-local`, with explicit static dev token only when declared | Compose service identity | environment variables and local files | Prometheus, Loki, Tempo, Grafana |
| `aws-ecs` | current primary edge uses workload-declared static bearer token | ECS task role plus GitHub OIDC for delivery | Secrets Manager or SSM injection | Prometheus-compatible signals routed by the runtime edge |

The current AWS edge does not standardize on Okta, Kong, OPA, or a JWT provider.
Those are valid future runtime choices, not workload metadata.

## Enterprise Candidate

`enterprise-runtime-candidate` is guidance, not an active runtime target. It
exists so enterprise teams see the intended standardization path before the
first adopter improvises one.

Allowed runtime-edge choices include:

- enterprise IdP at the edge, such as Okta, Entra ID, Auth0, or a managed IdP
- gateway or managed edge, such as Kong, Envoy, API Gateway, or equivalent
- runtime-owned policy engines, such as OPA or Cedar, only when policy
  distribution and ownership are explicit
- backend routing to Datadog, Splunk, New Relic, Elastic, Grafana, or another
  owned observability backend
- private connectivity, controlled egress, proxy, firewall, VPN, Direct Connect,
  PrivateLink, or an enterprise network equivalent

These tools must stay out of workload metadata unless the workload business
behavior genuinely depends on them.

## Decision Rules

A tool becomes a runtime default only when:

- multiple workloads share the need
- an operations or platform runtime owner exists
- it reduces app team burden
- it emits standard evidence
- it can be tested by conformance

A tool becomes workload-local only when:

- the app business behavior genuinely depends on it
- the dependency is tested locally
- failure modes are documented
- vendor or product mechanics do not leak into domain or application code

## App Team Interface

App teams should choose portable needs:

- exposure: public or internal
- caller type: user, service, or operator
- authorization location: app-local or runtime-policy-needed
- network needs: none, private ingress, private egress, or partner API
- evidence needs: subject, decision, request ID, run ID, status, artifact path

App teams should not choose per-workload products such as Okta, Kong, OPA,
Datadog, or Splunk unless the business behavior requires that product directly.
