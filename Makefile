# ─────────────────────────────────────────────────────────────────────────────
# Makefile — local dev, split-root infra, and operator commands
#
# Prerequisites (install once):
#   Recommended: open the repo in its dev container.
#   Native host tooling is optional; keep it aligned with docs/local-development.md.
#
# Usage:
#   make help                — list all targets
#   make dev                 — start local Postgres + PgBouncer
#   make local-up            — build/start app + local observability
#   make dapr-up             — build/start local Dapr order event runtime
#   make test                — run test suite
#   make runtime-conformance — build/run workload images against platform contract
#   make lint                — run all linters (app + infra)
#   make fmt                 — auto-format everything
#
#   make bootstrap           — one-time AWS account setup, idempotent
#
#   make infra-platform-plan — terraform plan for platform/bootstrap root
#   make infra-app-plan      — terraform plan for app-owned root
#
#   make app-deploy          — force new ECS deployment
#
#   make db-tunnel           — SSM port-forward localhost:LOCAL_PORT → RDS:5432
#   make db-exec             — open psql inside a running app task
#   make db-seed             — seed DB via SSM tunnel (idempotent)
#   make api-get-order ORDER_ID=1 FIELD=billing_email
# ─────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

AWS_REGION             := eu-central-1
ACCOUNT_ID             := 691627364817
TF_STATE_BUCKET        := aws-sdlc-containers-tfstate-$(ACCOUNT_ID)
ROOT_DOMAIN            ?= ersahinco-sandbox.eu
TF_PLATFORM_STATE_KEY  := aws-sdlc-containers/platform.tfstate
TF_APP_STATE_KEY       := aws-sdlc-containers/app.tfstate
TF_PLATFORM_VARS_FILE  := stack.tfvars
TF_APP_VARS_FILE       := stack.tfvars

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-24s %s\n", $$1, $$2}'

# ── Local dev ─────────────────────────────────────────────────────────────────

.PHONY: dev
dev: ## Start local Postgres + PgBouncer
	docker compose up -d db pgbouncer
	docker compose ps

.PHONY: observability
observability: ## Start local Prometheus + Loki + Promtail + Grafana
	docker compose --profile observability up -d prometheus loki tempo promtail grafana
	docker compose --profile observability ps

.PHONY: local-up
local-up: ## Build/start local app + Prometheus + Loki + Promtail + Grafana
	docker compose build app
	OTEL_TRACES_ENABLED=true docker compose --profile observability up -d db pgbouncer app prometheus loki tempo promtail grafana
	docker compose --profile observability ps

.PHONY: dapr-up
dapr-up: ## Build/start local Dapr order event runtime with LocalStack SNS/SQS
	docker compose build order-event-consumer
	docker compose --profile dapr up -d db localstack order-event-consumer order-event-consumer-dapr
	docker compose --profile dapr ps

.PHONY: local-down
local-down: ## Stop local app and observability services without deleting volumes
	docker compose --profile observability --profile dapr stop app prometheus loki tempo promtail grafana order-event-consumer order-event-consumer-dapr localstack

.PHONY: local-reset
local-reset: ## Stop all local services and delete Compose volumes
	docker compose --profile observability --profile tools --profile migration --profile data --profile dapr down -v --remove-orphans

.PHONY: observability-stop
observability-stop: ## Stop local observability services
	docker compose --profile observability stop prometheus loki tempo promtail grafana

.PHONY: migrate
migrate: ## Run Liquibase migrations against local DB
	docker compose --profile migration run --rm liquibase update

.PHONY: seed
seed: ## Seed local DB with test data
	uv run python scripts/data/seed_data.py

.PHONY: data-export
data-export: ## Run local data export job into the data_exports Docker volume
	docker compose --profile data run --rm data-export-job

.PHONY: test
test: ## Run test suite (requires local services and app running)
	uv run pytest tests/ -v

.PHONY: runtime-conformance
runtime-conformance: ## Build/run workload containers against the portable runtime contract
	uv run pytest tests/runtime -v --run-runtime-conformance

# ── Lint & format ─────────────────────────────────────────────────────────────

.PHONY: lint
lint: secret-scan dependency-audit lint-app lint-scripts lint-docs lint-workflows lint-dockerfiles lint-infra ## Run all linters

.PHONY: lint-app
lint-app: ## Lint and type-check Python
	uv run ruff check apps/ packages/ tests/ scripts/
	uv run pyright

.PHONY: lint-scripts
lint-scripts: ## Syntax-check shell scripts
	find scripts -name '*.sh' -print0 | xargs -0 bash -n

.PHONY: lint-docs
lint-docs: ## Check Markdown links
	lychee README.md 'docs/**/*.md'

.PHONY: lint-workflows
lint-workflows: ## Lint GitHub workflows
	actionlint

.PHONY: lint-dockerfiles
lint-dockerfiles: ## Lint Dockerfiles
	hadolint db/Dockerfile db/pgbouncer/Dockerfile apps/*/Dockerfile

.PHONY: secret-scan
secret-scan: ## Scan repository for committed secrets
	gitleaks dir . --redact --no-banner

.PHONY: dependency-audit
dependency-audit: ## Audit uv-locked Python dependencies for known vulnerabilities
	@tmpfile=$$(mktemp); \
	trap 'rm -f "$$tmpfile"' EXIT; \
	uv --quiet export --format requirements.txt --all-packages --all-groups --no-emit-project --no-emit-workspace --frozen --output-file "$$tmpfile"; \
	uv run pip-audit -r "$$tmpfile" --disable-pip --require-hashes --progress-spinner off --desc off --aliases off

.PHONY: lint-infra
lint-infra: ## Lint Terraform (fmt check + tflint + checkov)
	terraform fmt -check -recursive infra/
	cd infra/platform && tflint --init && tflint --format compact
	cd infra/app && tflint --init && tflint --format compact
	checkov -d infra --framework terraform --config-file infra/.checkov.yaml

.PHONY: fmt
fmt: ## Auto-format Python and Terraform
	uv run ruff format apps/ packages/ tests/ scripts/
	terraform fmt -recursive infra/

.PHONY: pre-commit
pre-commit: ## Install and run pre-commit hooks
	pre-commit install
	pre-commit run --all-files

# ── Infra — bootstrap (run once per AWS account) ──────────────────────────────

.PHONY: bootstrap
bootstrap: ## One-time AWS account setup — idempotent, safe to re-run
	@echo "--- S3 state bucket ---"
	@aws s3api head-bucket --bucket $(TF_STATE_BUCKET) 2>/dev/null \
		&& echo "  already exists, skipping" \
		|| ( \
			aws s3api create-bucket \
				--bucket $(TF_STATE_BUCKET) \
				--region $(AWS_REGION) \
				--create-bucket-configuration LocationConstraint=$(AWS_REGION) && \
			aws s3api put-bucket-versioning \
				--bucket $(TF_STATE_BUCKET) \
				--versioning-configuration Status=Enabled \
		)
	@echo "--- GitHub Actions OIDC provider ---"
	@aws iam list-open-id-connect-providers \
		--query 'OpenIDConnectProviderList[?ends_with(Arn, `token.actions.githubusercontent.com`)]' \
		--output text | grep -q . \
		&& echo "  already exists, skipping" \
		|| aws iam create-open-id-connect-provider \
			--url https://token.actions.githubusercontent.com \
			--client-id-list sts.amazonaws.com \
			--thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
	@echo "Bootstrap complete."

# ── Infra — split roots ───────────────────────────────────────────────────────

.PHONY: infra-platform-init
infra-platform-init:
	cd infra/platform && terraform init \
		-backend-config="key=$(TF_PLATFORM_STATE_KEY)" \
		-reconfigure

.PHONY: infra-platform-plan
infra-platform-plan: infra-platform-init ## Terraform plan — platform/bootstrap root
	cd infra/platform && terraform plan -var-file=$(TF_PLATFORM_VARS_FILE)

.PHONY: infra-platform-apply
infra-platform-apply: infra-platform-init ## Terraform apply — platform/bootstrap root
	cd infra/platform && terraform apply -var-file=$(TF_PLATFORM_VARS_FILE)

.PHONY: infra-app-init
infra-app-init:
	cd infra/app && terraform init \
		-backend-config="key=$(TF_APP_STATE_KEY)" \
		-reconfigure

.PHONY: infra-app-plan
infra-app-plan: infra-app-init ## Terraform plan — app-owned root
	cd infra/app && terraform plan -var-file=$(TF_APP_VARS_FILE)

.PHONY: infra-app-apply
infra-app-apply: infra-app-init ## Terraform apply — app-owned root
	cd infra/app && terraform apply -var-file=$(TF_APP_VARS_FILE)

.PHONY: infra-plan
infra-plan: infra-platform-plan infra-app-plan ## Terraform plan — platform then app roots

.PHONY: infra-apply
infra-apply: infra-platform-apply infra-app-apply ## Terraform apply — platform then app roots

# ── App — deploy ──────────────────────────────────────────────────────────────

.PHONY: app-deploy
app-deploy: ## Force new deployment of the existing ECS app service
	aws ecs update-service \
		--cluster aws-sdlc-containers \
		--service app \
		--task-definition aws-sdlc-containers \
		--force-new-deployment \
		--region $(AWS_REGION) \
		--query 'service.taskDefinition' \
		--output text

.PHONY: post-deploy-verify
post-deploy-verify: ## Verify deployed app readiness, metrics, modes, and ECS image
	@TOKEN="$${TOKEN:-$$(aws secretsmanager get-secret-value \
		--secret-id aws-sdlc-containers/api-token \
		--region $(AWS_REGION) \
		--query SecretString --output text)}" \
	BASE_URL="$${BASE_URL:-https://api.$(ROOT_DOMAIN)}" \
	ECS_CLUSTER="$${ECS_CLUSTER:-aws-sdlc-containers}" \
	ECS_SERVICE="$${ECS_SERVICE:-app}" \
	EXPECTED_TASK_FAMILY="$${EXPECTED_TASK_FAMILY:-aws-sdlc-containers}" \
	uv run python scripts/release/verify_post_deploy.py

.PHONY: observability-delivery-verify
observability-delivery-verify: ## Verify CloudWatch/Loki log delivery inventory and freshness
	@AWS_REGION="$(AWS_REGION)" \
	STACK_NAME="aws-sdlc-containers" \
	uv run python scripts/observability/verify_observability_delivery.py

.PHONY: release-event-delivery-verify
release-event-delivery-verify: ## Verify release-event push/query round-trip through Loki
	@AWS_REGION="$(AWS_REGION)" \
	STACK_NAME="aws-sdlc-containers" \
	uv run python scripts/observability/verify_release_event_loki_delivery.py

.PHONY: observability-cloud-traffic
observability-cloud-traffic: ## Generate live API traffic and small cloud probes for Grafana/CloudWatch observation
	@AWS_REGION="$(AWS_REGION)" \
	BASE_URL="$${BASE_URL:-https://api.$(ROOT_DOMAIN)}" \
	uv run python scripts/observability/generate_cloud_traffic.py
	@AWS_REGION="$(AWS_REGION)" \
	STACK_NAME="aws-sdlc-containers" \
	uv run python scripts/observability/run_observability_cloud_jobs.py

.PHONY: observability-cloud-jobs
observability-cloud-jobs: ## Run only the small cloud probes for quiet observability log groups
	@AWS_REGION="$(AWS_REGION)" \
	STACK_NAME="aws-sdlc-containers" \
	uv run python scripts/observability/run_observability_cloud_jobs.py

.PHONY: incident-evidence
incident-evidence: ## Build portable Markdown/JSON incident evidence bundle
	@AWS_REGION="$(AWS_REGION)" \
	STACK_NAME="aws-sdlc-containers" \
	ROOT_DOMAIN="$(ROOT_DOMAIN)" \
	uv run python scripts/observability/incident_evidence_bundle.py

# ── DB access — no bastion needed ─────────────────────────────────────────────
#
# All three targets delegate to shell scripts under scripts/ to avoid Make's
# $(shell ...) quoting limitations with JMESPath backtick filters.
#
# Prerequisites:
#   AWS CLI Session Manager plugin installed from AWS's official channel.
# ─────────────────────────────────────────────────────────────────────────────

LOCAL_PORT         ?= 15432
SEED_NUM_CUSTOMERS ?= 1000
SEED_NUM_ORDERS    ?= 10000

.PHONY: db-tunnel
db-tunnel: ## SSM port-forward localhost:$(LOCAL_PORT) → RDS:5432
	@bash scripts/operator/db_tunnel.sh $(LOCAL_PORT) $(AWS_REGION)

.PHONY: db-exec
db-exec: ## Open psql inside a running app task
	@bash scripts/operator/db_exec.sh $(AWS_REGION)

.PHONY: db-seed
db-seed: ## Seed DB via SSM tunnel  (SEED_NUM_CUSTOMERS=1000, SEED_NUM_ORDERS=10000)
	@bash scripts/operator/db_seed_tunnel.sh $(SEED_NUM_CUSTOMERS) $(SEED_NUM_ORDERS) $(AWS_REGION)

# ── API smoke query ───────────────────────────────────────────────────────────
#
# Fetches a single order from the live API and prints the full response or a
# single field. Requires the single HTTPS entrypoint and fixed-token auth.
#
# Usage:
#   make api-get-order ORDER_ID=1           — full order JSON
#   make api-get-order ORDER_ID=42 FIELD=billing_email
#
# FIELD can be any top-level key in the OrderResponse schema:
#   id, customer_id, total_amount, status, submitted_at, created_at, billing_email
# ─────────────────────────────────────────────────────────────────────────────

ORDER_ID ?= 1
FIELD    ?=

.PHONY: api-get-order
api-get-order: ## Query a live order by ID  (ORDER_ID=1, FIELD=billing_email)
	@API_HOST="api.$(ROOT_DOMAIN)" && \
	AUTH_TOKEN="$${TOKEN:-}" && \
	if [ -z "$$AUTH_TOKEN" ]; then \
		AUTH_TOKEN=$$(aws secretsmanager get-secret-value \
			--secret-id aws-sdlc-containers/api-token \
			--region $(AWS_REGION) \
			--query SecretString --output text); \
	fi && \
	RESPONSE=$$(curl -sf \
		-H "Authorization: Bearer $$AUTH_TOKEN" \
		"https://$$API_HOST/orders/$(ORDER_ID)") && \
	if [ -n "$(FIELD)" ]; then \
		echo "$$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('$(FIELD)', 'field not found'))"; \
	else \
		echo "$$RESPONSE" | python3 -m json.tool; \
	fi
