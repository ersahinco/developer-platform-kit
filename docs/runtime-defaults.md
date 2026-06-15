# Runtime Defaults

Opinionated runtime defaults for enterprise DevEx standardization.

The toolkit is intentionally opinionated, but the machinery lives at the
runtime and capability layer. Workloads declare needs and emit standard
evidence. Runtime targets choose the blessed implementation.

Machine-readable defaults live in `platform/runtime-defaults.json`.
Inspect active defaults with:

```bash
make runtime-defaults
make capability-implementation-matrix
make local-compose-live-proof
```

## Active Runtime Targets

| Runtime target | Authn default | Authz/policy default | Network default | CI/CD default | Observability default |
|---|---|---|---|---|---|
| `local-compose` | `none-local`, with explicit static dev token only when declared | app-local checks when needed plus local Conftest policy checks | Compose network and explicit host ports | local Make targets plus pytest/runtime conformance | Prometheus, Loki, Tempo, Grafana |
| `local-kubernetes` | `none-local`, with explicit static dev token only when declared | app-local checks when needed plus manifest/contract policy checks | kind cluster, ClusterIP Services, probes, sidecars, and in-cluster DNS | local Make targets, kind image loading, `kubectl apply -k`, smoke checks, Dapr proof, and evidence drill | pod logs, daprd logs, events, endpoints, and Prometheus endpoints |
| `aws-ecs` | current primary edge uses workload-declared static bearer token | app-local business authz plus repo policy checks | ALB ingress, private ECS placement, VPC security groups | GitHub Actions OIDC, immutable tags, reviewed delivery, release evidence | Prometheus-compatible signals routed to CloudWatch and optional ADOT |

The current AWS edge does not standardize on Okta, Kong, OPA, or a JWT provider.
Those are valid future runtime choices, not workload metadata.

## Live Local Drill

Static runtime default proof lives in `tests/contracts/test_runtime_defaults_contract.py`
and the inventory views above. Candidate enterprise tools stay candidate-only;
the contract checks point at real files, tests, workflows, and evidence seams
instead of promoting a product choice.

`make local-compose-live-proof` runs a dedicated temporary Compose project
with token auth enabled, proves live health, readiness, metrics, auth 401/200,
structured logs, Prometheus, Loki, Tempo, and Grafana, then tears the stack down
by default. Use `--keep-stack` on `scripts/platform/local_compose_live_proof.py`
only when you want to inspect the drill stack manually.

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

Before promoting any candidate enterprise capability, update
`platform/runtime-defaults.json` and the runtime default contract tests. A
candidate runtime capability becomes active only when it has owner, config
surface, conformance test, evidence artifact, failure mode, and runbook.

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
