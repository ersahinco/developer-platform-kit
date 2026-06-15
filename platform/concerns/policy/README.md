# Policy Concern

Shared policy artifacts for repo and delivery-edge enforcement.

Current tool: OPA via Conftest.

Current scope:

- `.github/workflows/*.yml`
- `platform/workloads.json`
- `platform/runtime-conformance.json`
- `platform/platform-inventory.json`
- `platform/runtime-defaults.json`

Command:

```bash
make lint-policy
```

Rule: keep policy close to standard tools and structured inputs. Use OPA for
repo-specific guardrails that are awkward in generic linters, not as a second
application framework.
