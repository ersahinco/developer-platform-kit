# ─────────────────────────────────────────────────────────────────────────────
# Makefile — local dev, lint, and infra bootstrap commands
#
# Prerequisites (install once):
#   brew install uv terraform tflint checkov pre-commit
#   pip install checkov   # or: brew install checkov
#
# Usage:
#   make help             — list all targets
#   make dev              — start local stack
#   make test             — run test suite
#   make lint             — run all linters (app + infra)
#   make fmt              — auto-format everything
#   make bootstrap        — one-time AWS account setup, idempotent (safe to re-run)
#   make plan-dev         — terraform plan for dev
#   make apply-dev        — terraform apply for dev
#   make apply-iam-dev    — targeted apply: IAM policy only (breaks bootstrap cycle)
#   make plan-prod        — terraform plan for prod
#   make apply-prod       — terraform apply for prod
# ─────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

AWS_REGION      := eu-central-1
ACCOUNT_ID      := 691627364817
TF_STATE_BUCKET := db-migration-example-tfstate-$(ACCOUNT_ID)
TF_LOCK_TABLE   := terraform-locks

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

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

.PHONY: init-dev
init-dev: ## terraform init for dev state
	cd infra && terraform init \
		-backend-config="key=db-migration-example/dev.tfstate" \
		-reconfigure

.PHONY: plan-dev
plan-dev: init-dev ## terraform plan for dev
	cd infra && terraform plan -var-file=dev.tfvars

.PHONY: apply-dev
apply-dev: init-dev ## terraform apply for dev
	cd infra && terraform apply -var-file=dev.tfvars

.PHONY: apply-iam-dev
apply-iam-dev: init-dev ## Targeted apply: IAM role + policy only — use to break bootstrap permission cycle
	cd infra && terraform apply -var-file=dev.tfvars \
		-target=aws_iam_role.github_actions \
		-target=aws_iam_role_policy.github_actions

.PHONY: destroy-dev
destroy-dev: init-dev ## terraform destroy for dev (sprint reset)
	cd infra && terraform destroy -var-file=dev.tfvars

# ── Infra — prod ──────────────────────────────────────────────────────────────

.PHONY: init-prod
init-prod: ## terraform init for prod state
	cd infra && terraform init \
		-backend-config="key=db-migration-example/prod.tfstate" \
		-reconfigure

.PHONY: plan-prod
plan-prod: init-prod ## terraform plan for prod
	cd infra && terraform plan -var-file=prod.tfvars

.PHONY: apply-prod
apply-prod: init-prod ## terraform apply for prod
	cd infra && terraform apply -var-file=prod.tfvars

.PHONY: apply-iam-prod
apply-iam-prod: init-prod ## Targeted apply: IAM role + policy only for prod
	cd infra && terraform apply -var-file=prod.tfvars \
		-target=aws_iam_role.github_actions \
		-target=aws_iam_role_policy.github_actions
