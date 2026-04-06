# ─────────────────────────────────────────────────────────────────────────────
# Makefile — local dev, lint, and infra bootstrap commands
#
# Prerequisites (install once):
#   brew install uv terraform tflint checkov pre-commit session-manager-plugin
#
# Usage:
#   make help                — list all targets
#   make dev                 — start local stack
#   make test                — run test suite
#   make lint                — run all linters (app + infra)
#   make fmt                 — auto-format everything
#
#   make bootstrap           — one-time AWS account setup, idempotent
#
#   make infra-plan-dev      — terraform plan for dev
#   make infra-apply-dev     — terraform apply for dev
#   make infra-plan-prod     — terraform plan for prod
#   make infra-apply-prod    — terraform apply for prod
#
#   make app-deploy-dev      — force new ECS deployment in dev
#   make app-deploy-prod     — force new ECS deployment in prod
#
#   make db-tunnel ENV=dev   — SSM port-forward localhost:LOCAL_PORT → RDS:5432
#   make db-exec ENV=dev     — open psql inside a running app task
#   make db-seed ENV=prod    — seed prod DB via SSM tunnel (idempotent)
# ─────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

AWS_REGION      := eu-central-1
ACCOUNT_ID      := 691627364817
TF_STATE_BUCKET := db-migration-example-tfstate-$(ACCOUNT_ID)
TF_LOCK_TABLE   := terraform-locks

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-24s %s\n", $1, $2}'

# ── Local dev ─────────────────────────────────────────────────────────────────

.PHONY: dev
dev: ## Start local Postgres + PgBouncer + app
	docker compose up -d db pgbouncer
	docker compose ps

.PHONY: migrate
migrate: ## Run Liquibase migrations against local DB
	./scripts/run_liquibase.sh update

.PHONY: seed
seed: ## Seed local DB with test data
	uv run python scripts/seed_data.py

.PHONY: test
test: ## Run test suite (requires local stack running)
	uv run pytest tests/ -v

# ── Lint & format ─────────────────────────────────────────────────────────────

.PHONY: lint
lint: lint-app lint-infra ## Run all linters

.PHONY: lint-app
lint-app: ## Lint Python (ruff)
	uv run ruff check app/ tests/ scripts/

.PHONY: lint-infra
lint-infra: ## Lint Terraform (fmt check + tflint + checkov)
	terraform fmt -check -recursive infra/
	cd infra && tflint --init && tflint --format compact
	checkov -d infra --framework terraform --config-file infra/.checkov.yaml

.PHONY: fmt
fmt: ## Auto-format Python and Terraform
	uv run ruff format app/ tests/ scripts/
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

# ── Infra — dev ───────────────────────────────────────────────────────────────

.PHONY: infra-init-dev
infra-init-dev:
	cd infra && terraform init \
		-backend-config="key=db-migration-example/dev.tfstate" \
		-reconfigure

.PHONY: infra-plan-dev
infra-plan-dev: infra-init-dev ## Terraform plan — dev
	cd infra && terraform plan -var-file=dev.tfvars

.PHONY: infra-apply-dev
infra-apply-dev: infra-init-dev ## Terraform apply — dev
	cd infra && terraform apply -var-file=dev.tfvars

.PHONY: infra-apply-iam-dev
infra-apply-iam-dev: infra-init-dev ## Targeted apply: IAM only — breaks bootstrap permission cycle (dev)
	cd infra && terraform apply -var-file=dev.tfvars \
		-target=aws_iam_role.github_actions \
		-target=aws_iam_role_policy.github_actions

.PHONY: infra-destroy-dev
infra-destroy-dev: infra-init-dev ## Terraform destroy — dev (sprint reset)
	cd infra && terraform destroy -var-file=dev.tfvars

# ── Infra — prod ──────────────────────────────────────────────────────────────

.PHONY: infra-init-prod
infra-init-prod:
	cd infra && terraform init \
		-backend-config="key=db-migration-example/prod.tfstate" \
		-reconfigure

.PHONY: infra-plan-prod
infra-plan-prod: infra-init-prod ## Terraform plan — prod
	cd infra && terraform plan -var-file=prod.tfvars

.PHONY: infra-apply-prod
infra-apply-prod: infra-init-prod ## Terraform apply — prod
	cd infra && terraform apply -var-file=prod.tfvars

.PHONY: infra-apply-iam-prod
infra-apply-iam-prod: infra-init-prod ## Targeted apply: IAM only — breaks bootstrap permission cycle (prod)
	cd infra && terraform apply -var-file=prod.tfvars \
		-target=aws_iam_role.github_actions \
		-target=aws_iam_role_policy.github_actions

# ── App — deploy ──────────────────────────────────────────────────────────────

.PHONY: app-deploy-dev
app-deploy-dev: ## Force new ECS deployment — dev (picks up latest task definition)
	aws ecs update-service \
		--cluster db-migration-example-dev \
		--service app \
		--task-definition db-migration-example-dev \
		--force-new-deployment \
		--region $(AWS_REGION) \
		--query 'service.taskDefinition' \
		--output text

.PHONY: app-deploy-prod
app-deploy-prod: ## Force new ECS deployment — prod (picks up latest task definition)
	aws ecs update-service \
		--cluster db-migration-example-prod \
		--service app \
		--task-definition db-migration-example-prod \
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

ENV                ?= dev
LOCAL_PORT         ?= 15432
SEED_NUM_CUSTOMERS ?= 1000
SEED_NUM_ORDERS    ?= 10000

.PHONY: db-tunnel
db-tunnel: ## SSM port-forward localhost:$(LOCAL_PORT) → RDS:5432  (ENV=dev|prod, LOCAL_PORT=15432)
	@bash scripts/db_tunnel.sh $(ENV) $(LOCAL_PORT) $(AWS_REGION)

.PHONY: db-exec
db-exec: ## Open psql inside a running app task  (ENV=dev|prod)
	@bash scripts/db_exec.sh $(ENV) $(AWS_REGION)

.PHONY: db-seed
db-seed: ## Seed DB via SSM tunnel  (ENV=dev|prod, SEED_NUM_CUSTOMERS=1000, SEED_NUM_ORDERS=10000)
	@bash scripts/db_seed_tunnel.sh $(ENV) $(SEED_NUM_CUSTOMERS) $(SEED_NUM_ORDERS) $(AWS_REGION)
