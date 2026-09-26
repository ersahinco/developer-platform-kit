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
	uv run python -m scaffold.new_repo list

.PHONY: describe
describe: ## Show one template's variables: make describe TEMPLATE=app
	uv run python -m scaffold.new_repo describe $(TEMPLATE)

################################################################################
# Checks
################################################################################

.PHONY: lint
lint: lint-python lint-workflows lint-terraform ## Run every linter

.PHONY: lint-python
lint-python: ## Format check, lint, and type check the scaffolder and tests
	uv run ruff format --check scaffold/ tests/
	uv run ruff check scaffold/ tests/
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
	uv run ruff format scaffold/ tests/
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
	uvx --python 3.12 --from checkov==3.3.8 checkov --directory modules --framework terraform --config-file .checkov.yaml --compact

.PHONY: lint-dockerfiles
lint-dockerfiles: ## Lint the Dockerfiles as rendered. A template with __TOKEN__ in it is not valid Dockerfile
	@tmp=$$(mktemp -d); status=0; \
	uv run python -m scaffold.new_repo render-examples "$$tmp" > /dev/null; \
	find "$$tmp" -name Dockerfile -print0 | xargs -0 hadolint || status=$$?; \
	rm -rf "$$tmp"; \
	exit $$status

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
