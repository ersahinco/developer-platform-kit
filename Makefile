.DEFAULT_GOAL := help
SHELL := bash

MODULES := $(sort $(dir $(wildcard modules/aws/*/)))
TF_DIRS := modules repo-templates tests

.PHONY: help
help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

# Scaffolding

.PHONY: templates
templates: ## List available repo templates
	python3 -m scaffold.new_repo list

.PHONY: describe
describe: ## Show one template's variables: make describe TEMPLATE=app
	python3 -m scaffold.new_repo describe $(TEMPLATE)

.PHONY: cli-install cli-build cli-check
cli-install: ## Install dpk and dpk-backstage as isolated user tools (requires uv)
	uv tool install --reinstall .

cli-build: ## Build the CLI wheel and source archive in dist/ (requires uv)
	uv build

cli-check: ## Build/install the CLI outside this checkout and compare all outputs
	@set -euo pipefail; built=$$(mktemp -d); trap 'rm -rf "$$built"' EXIT; \
	uv build --out-dir "$$built"; \
	uv run python -m tests.validate_package "$$built"

.PHONY: portal
portal: ## Show local portal URLs and setup commands
	@printf '%s\n' 'Backstage: https://cnoe.localtest.me:8443' \
	  'Keycloak admin: https://cnoe.localtest.me:8443/keycloak/admin/' \
	  'Credentials: make portal-credentials' \
	  'GitHub login: make portal-identity PROVIDER=github' \
	  'GitHub publishing: make portal-github OWNER=YOUR_GITHUB_OWNER' \
	  'Start/update: make portal-up'

.PHONY: portal-prepare portal-check portal-up portal-status portal-credentials portal-smoke portal-verify portal-identity portal-github portal-down
portal-%: export KUBECONFIG := $(CURDIR)/platform/.local/kubeconfig
portal-%: export PORTAL_SET := $(PORTAL_SET)
portal-prepare: ## Assemble pinned CNOE packages and export templates
	python3 platform/prepare.py

.PHONY: portal-image
portal-image: export PORTAL_IMAGE = $(IMAGE)
portal-image: ## Build the shared Entra portal image: IMAGE=registry/name:version
	@[[ "$$PORTAL_IMAGE" =~ :[A-Za-z0-9_][A-Za-z0-9_.-]*$$ && "$$PORTAL_IMAGE" != *:latest ]] || \
	  { echo 'Set IMAGE=registry/name:version; latest is not allowed'; exit 2; }
	docker build --provenance=false --tag "$$PORTAL_IMAGE" platform/backstage

PORTAL_COMPOSE = docker compose --env-file platform/.local/portal.env -f platform/hosting/compose.yaml
.PHONY: portal-host-up portal-host-status portal-host-down hosting-check
portal-host-up: ## Start the shared portal on this host using platform/.local/portal.env
	@$(PORTAL_COMPOSE) config --quiet
	@image=$$($(PORTAL_COMPOSE) config --images); [[ "$$image" =~ @sha256:[a-f0-9]{64}$$ ]] || \
	  { echo 'PORTAL_IMAGE must be pinned by digest'; exit 2; }
	$(PORTAL_COMPOSE) up -d --wait --wait-timeout 180

portal-host-status: ## Show the shared host's portal state
	$(PORTAL_COMPOSE) ps

portal-host-down: ## Stop the shared host's portal; the external database remains
	$(PORTAL_COMPOSE) down

hosting-check: ## Validate native on-premises and AWS hosting definitions without deploying
	PORTAL_IMAGE=registry.example.com/backstage@sha256:$$(printf '0%.0s' {1..64}) \
	  PORTAL_ENV_FILE=$(CURDIR)/platform/hosting/portal.env.example \
	  docker compose -f platform/hosting/compose.yaml config --quiet
	uvx --from cfn-lint==1.57.0 cfn-lint platform/hosting/aws.yaml

portal-check: portal-prepare ## Validate CNOE overlays and test the Backstage image without deploying
	docker build --provenance=false --iidfile platform/.local/check-image-id platform/backstage
	@set -euo pipefail; exported=$$(mktemp -d); trap 'rm -rf "$$exported"' EXIT; \
	python3 -m scaffold.backstage "$$exported/templates" --allowed-owner acme --github-settings tests/fixtures/github-settings.json; \
	docker run --rm --network none -v "$$exported/templates:/templates:ro" \
	  --entrypoint node "$$(cat platform/.local/check-image-id)" --test platform/github.test.cjs platform/runtime.test.cjs
	bash tests/hosting/check.sh

portal-up: portal-prepare ## Start or update Backstage and Keycloak locally
	@if ! kubectl --request-timeout=5s get deployment/external-secrets-webhook -n external-secrets >/dev/null 2>&1; then \
		idpbuilder create --name toolkit --kube-version v1.33.1 --use-path-routing --no-exit=false --package platform/.local/packages/external-secrets.yaml; \
	fi
	kubectl wait -n external-secrets --for=create deployment/external-secrets-webhook --timeout=180s
	kubectl rollout status -n external-secrets deployment/external-secrets-webhook --timeout=180s
	python3 platform/runtime.py
	python3 platform/image.py
	idpbuilder create --name toolkit --kube-version v1.33.1 --use-path-routing --no-exit=false $(foreach package,external-secrets keycloak backstage backstage-templates,--package platform/.local/packages/$(package).yaml)
	kubectl wait -n backstage --for=create deployment/backstage --timeout=600s
	kubectl rollout status -n backstage deployment/backstage --timeout=600s
	python3 platform/identity.py prepare
	python3 platform/bootstrap.py

portal-status: ## Show local platform rollout status
	kubectl get applications -n argocd
	kubectl get applications -n argocd -o go-template='{{range .items}}{{$$name := .metadata.name}}{{range .status.conditions}}{{printf "%s: %s: %s\n" $$name .type .message}}{{end}}{{end}}'
	kubectl get pods -n backstage

portal-credentials: ## Show only the local Keycloak user and admin login passwords
	@printf '%s\n' 'Keep these passwords in your terminal; do not paste this output into chat or Git.'
	@kubectl get secret keycloak-config -n keycloak -o go-template='USER_PASSWORD={{index .data "USER_PASSWORD" | base64decode}}{{"\n"}}KEYCLOAK_ADMIN_PASSWORD={{index .data "KEYCLOAK_ADMIN_PASSWORD" | base64decode}}{{"\n"}}'

portal-github: ## Set the GitHub publishing token: OWNER=your-owner
	python3 platform/runtime.py --github-owner "$(OWNER)"

portal-verify: ## Check live identity, permissions, TLS, and destination restrictions
	python3 platform/verify.py

portal-identity: ## Connect a sign-in provider: PROVIDER=github
	python3 platform/identity.py $(PROVIDER)

portal-smoke: ## Publish all three starters to local Gitea and compare CLI output
	python3 platform/smoke.py

portal-down: ## Delete the local cluster and its repositories
	idpbuilder delete --name toolkit

# Checks

.PHONY: lint
lint: lint-python lint-workflows lint-terraform ## Run every linter

.PHONY: lint-python
lint-python: ## Check Python formatting, lint, and scaffolder types
	uv run ruff format --check scaffold/ tests/ platform/
	uv run ruff check scaffold/ tests/ platform/
	uv run pyright

.PHONY: lint-workflows
lint-workflows: ## Lint this repo's workflows and the workflows inside templates
	actionlint .github/workflows/*.yml
	actionlint repo-templates/*/files/.github/workflows/*.yml

.PHONY: lint-terraform
lint-terraform: ## Check Terraform formatting across modules and templates
	@set -e; for dir in $(TF_DIRS); do terraform fmt -check -recursive $$dir; done

.PHONY: fmt
fmt: ## Fix formatting in place
	uv run ruff format scaffold/ tests/ platform/
	@set -e; for dir in $(TF_DIRS); do terraform fmt -recursive $$dir; done

.PHONY: validate-modules
validate-modules: ## terraform validate every module in isolation
	@set -e; for module in $(MODULES); do \
		echo "== $$module"; \
		terraform -chdir=$$module init -backend=false -input=false > /dev/null; \
		terraform -chdir=$$module validate; \
	done

.PHONY: lint-tflint
lint-tflint: ## TFLint every module
	@set -e; for module in $(MODULES); do \
		echo "== $$module"; \
		(cd $$module && tflint --init > /dev/null && tflint --format compact); \
	done

.PHONY: lint-checkov
lint-checkov: ## Checkov scan of the modules
	uvx --python 3.12 --from checkov==3.3.19 checkov --directory modules --framework terraform --quiet --compact

.PHONY: lint-dockerfiles
lint-dockerfiles: ## Lint the Dockerfiles as rendered. A template with __TOKEN__ in it is not valid Dockerfile
	@set -euo pipefail; tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	uv run python -m scaffold.new_repo render-examples "$$tmp" > /dev/null; \
	find "$$tmp" -name Dockerfile -print0 | xargs -0 hadolint

.PHONY: secret-scan
secret-scan: ## Scan the repo for committed secrets
	gitleaks dir . --redact --no-banner

.PHONY: test
test: ## Render every template and check the output
	uv run python -m pytest tests/ -v

.PHONY: check
check: lint test cli-check hosting-check validate-modules validate-templates lint-tflint lint-checkov lint-dockerfiles ## What CI runs

.PHONY: validate-templates
validate-templates: ## Validate the rendered infra root against local modules
	uv run python -m tests.validate_terraform
