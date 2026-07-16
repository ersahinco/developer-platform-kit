# Security Concern

Shared runtime security capability owned at the platform edge.

The toolkit keeps security machinery opinionated without putting product
choices into workload metadata. Workloads declare needs and emit evidence;
runtime targets realize those needs.

Current defaults live in `platform/runtime-defaults.json`:

- `edge_auth`: local defaults are unauthenticated unless an explicit dev token
  is declared; the current AWS primary edge uses workload-enforced static bearer
  auth.
- `authz_policy`: business authorization stays app-local by default; shared
  OPA/Conftest policy validates repository contracts and platform metadata.
- `secrets_injection`: local runs use env/local files; AWS uses Secrets
  Manager or SSM through ECS task definitions.
- `service_identity`: local uses Compose service identity; AWS uses ECS task
  roles and GitHub OIDC delivery identity.

Add another runtime security tool only for a shared, owned, evidence-producing,
and conformance-tested workload need.
