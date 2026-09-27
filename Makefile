.DEFAULT_GOAL := help
SHELL := bash

MODULES := $(sort $(dir $(wildcard modules/aws/*/)))
TF_DIRS := modules repo-templates

.PHONY: help
help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

################################################################################
# Scaffolding
################################################################################

.PHONY: templates
templates: ## List available repo templates
	python3 -m scaffold.new_repo list

.PHONY: describe
describe: ## Show one template's variables: make describe TEMPLATE=app
	python3 -m scaffold.new_repo describe $(TEMPLATE)

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
portal-prepare: ## Assemble pinned CNOE packages and export templates
	python3 platform/prepare.py

portal-check: portal-prepare ## Validate CNOE overlays and test the Backstage image without deploying
	docker build --provenance=false --platform linux/amd64 platform/backstage

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

################################################################################
# Checks
################################################################################

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
	uvx --python 3.12 --from checkov==3.3.8 checkov --directory modules --framework terraform --quiet --compact

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
check: lint test validate-modules validate-templates lint-tflint lint-checkov lint-dockerfiles ## What CI runs

.PHONY: validate-templates
validate-templates: ## Validate the rendered infra root against local modules
	uv run python -m tests.validate_terraform
