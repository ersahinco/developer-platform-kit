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
and the inventory views above. The contract checks point at real files, tests,
workflows, and evidence seams.

`make local-compose-live-proof` runs a dedicated temporary Compose project
with token auth enabled, proves live health, readiness, metrics, auth 401/200,
structured logs, Prometheus, Loki, Tempo, and Grafana, then tears the stack down
by default. Use `--keep-stack` on `scripts/platform/local_compose_live_proof.py`
only when you want to inspect the drill stack manually.

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
