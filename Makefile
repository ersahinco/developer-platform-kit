# ─────────────────────────────────────────────────────────────────────────────
# Makefile — local dev, single-stack infra, and operator commands
#
# Prerequisites (install once):
#   brew install uv terraform tflint checkov pre-commit session-manager-plugin
#
# Usage:
#   make help                — list all targets
#   make dev                 — start local Postgres + PgBouncer
#   make test                — run test suite
#   make lint                — run all linters (app + infra)
#   make fmt                 — auto-format everything
#
#   make bootstrap           — one-time AWS account setup, idempotent
#
#   make infra-plan          — terraform plan for the single stack
#   make infra-apply         — terraform apply for the single stack
#
#   make app-deploy          — force new ECS deployment
#
#   make db-tunnel           — SSM port-forward localhost:LOCAL_PORT → RDS:5432
#   make db-exec             — open psql inside a running app task
#   make db-seed             — seed DB via SSM tunnel (idempotent)
#   make api-get-order ORDER_ID=1 FIELD=billing_email
# ─────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

AWS_REGION      := eu-central-1
ACCOUNT_ID      := 691627364817
TF_STATE_BUCKET := aws-sdlc-containers-tfstate-$(ACCOUNT_ID)
TF_LOCK_TABLE   := terraform-locks
ROOT_DOMAIN     ?= ersahinco-sandbox.eu
TF_STATE_KEY    := aws-sdlc-containers/stack.tfstate
TF_VARS_FILE    := stack.tfvars

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
	docker compose --profile observability up -d prometheus loki promtail grafana
	docker compose --profile observability ps

.PHONY: observability-stop
observability-stop: ## Stop local observability services
	docker compose --profile observability stop prometheus loki promtail grafana

.PHONY: migrate
migrate: ## Run Liquibase migrations against local DB
	./scripts/run_liquibase.sh update

.PHONY: seed
seed: ## Seed local DB with test data
	uv run python scripts/seed_data.py

.PHONY: data-export
data-export: ## Run local data export job into the data_exports Docker volume
	docker compose --profile data run --rm data-export-job

.PHONY: test
test: ## Run test suite (requires local services and app running)
	uv run pytest tests/ -v

# ── Lint & format ─────────────────────────────────────────────────────────────

.PHONY: lint
lint: secret-scan dependency-audit lint-app lint-scripts lint-docs lint-infra ## Run all linters

.PHONY: lint-app
lint-app: ## Lint and type-check Python
	uv run ruff check apps/ packages/ tests/ scripts/
	uv run pyright

.PHONY: lint-scripts
lint-scripts: ## Syntax-check shell scripts
	bash -n scripts/*.sh

.PHONY: lint-docs
lint-docs: ## Check local Markdown links
	python3 scripts/check_docs_links.py

.PHONY: secret-scan
secret-scan: ## Scan repository for high-confidence committed secrets
	uv run python scripts/secret_scan.py .

.PHONY: dependency-audit
dependency-audit: ## Audit uv-locked Python dependencies for known vulnerabilities
	uv run python scripts/dependency_audit.py

.PHONY: lint-infra
lint-infra: ## Lint Terraform (fmt check + tflint + checkov)
	terraform fmt -check -recursive infra/
	cd infra && tflint --init && tflint --format compact
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
	@echo "--- DynamoDB lock table ---"
	@aws dynamodb describe-table --table-name $(TF_LOCK_TABLE) --region $(AWS_REGION) 2>/dev/null \
		&& echo "  already exists, skipping" \
		|| aws dynamodb create-table \
			--table-name $(TF_LOCK_TABLE) \
			--attribute-definitions AttributeName=LockID,AttributeType=S \
			--key-schema AttributeName=LockID,KeyType=HASH \
			--billing-mode PAY_PER_REQUEST \
			--region $(AWS_REGION)
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

# ── Infra — single stack ──────────────────────────────────────────────────────
#
# All targets below operate on the same long-lived stack. This repo does not
# maintain separate dev/prod Terraform states or promotion environments.
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: infra-init
infra-init:
	cd infra && terraform init \
		-backend-config="key=$(TF_STATE_KEY)" \
		-reconfigure

.PHONY: infra-plan
infra-plan: infra-init ## Terraform plan — single stack
	cd infra && terraform plan -var-file=$(TF_VARS_FILE)

.PHONY: infra-apply
infra-apply: infra-init ## Terraform apply — single stack
	cd infra && terraform apply -var-file=$(TF_VARS_FILE)

.PHONY: infra-apply-iam
infra-apply-iam: infra-init ## Targeted apply: GitHub Actions IAM only — breaks bootstrap permission cycle
	cd infra && terraform apply -var-file=$(TF_VARS_FILE) \
		-target=aws_iam_role.github_actions \
		-target=aws_iam_policy.github_actions_state_access \
		-target=aws_iam_policy.github_actions_compute_deploy \
		-target=aws_iam_policy.github_actions_ecr \
		-target=aws_iam_policy.github_actions_networking \
		-target=aws_iam_policy.github_actions_edge_dns \
		-target=aws_iam_policy.github_actions_logs_secrets \
		-target=aws_iam_policy.github_actions_data_hub \
		-target=aws_iam_policy.github_actions_identity_kms \
		-target=aws_iam_policy.github_actions_networking_vpc_endpoints \
		-target=aws_iam_policy.github_actions_edge_waf \
		-target=aws_iam_role_policy_attachment.github_actions_managed \
		-target=aws_iam_role_policy_attachment.github_actions_networking_vpc_endpoints \
		-target=aws_iam_role_policy_attachment.github_actions_edge_waf

.PHONY: infra-destroy
infra-destroy: infra-init ## Terraform destroy — single stack
	cd infra && terraform destroy -var-file=$(TF_VARS_FILE)

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

# ── DB access — no bastion needed ─────────────────────────────────────────────
#
# All three targets delegate to shell scripts under scripts/ to avoid Make's
# $(shell ...) quoting limitations with JMESPath backtick filters.
#
# Prerequisites:
#   brew install session-manager-plugin
# ─────────────────────────────────────────────────────────────────────────────

LOCAL_PORT         ?= 15432
SEED_NUM_CUSTOMERS ?= 1000
SEED_NUM_ORDERS    ?= 10000

.PHONY: db-tunnel
db-tunnel: ## SSM port-forward localhost:$(LOCAL_PORT) → RDS:5432
	@bash scripts/db_tunnel.sh $(LOCAL_PORT) $(AWS_REGION)

.PHONY: db-exec
db-exec: ## Open psql inside a running app task
	@bash scripts/db_exec.sh $(AWS_REGION)

.PHONY: db-seed
db-seed: ## Seed DB via SSM tunnel  (SEED_NUM_CUSTOMERS=1000, SEED_NUM_ORDERS=10000)
	@bash scripts/db_seed_tunnel.sh $(SEED_NUM_CUSTOMERS) $(SEED_NUM_ORDERS) $(AWS_REGION)

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
