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
#   make dapr-up             — build/start local Dapr event consumer runtime
#   make platform-toolkit-validate-local
#                             — prove the local workload journey end to end
#   make test                — run test suite
#   make runtime-conformance — build/run workload images against platform contract
#   make platform-toolkit-validate-cloud
#                             — run safe cloud readiness checks without mutating AWS
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

STACK_NAME             ?= $(notdir $(CURDIR))
AWS_REGION             ?= eu-central-1
ACCOUNT_ID             ?= $(shell aws sts get-caller-identity --query Account --output text 2>/dev/null)
LOCAL_DATABASE_URL     ?= postgresql://postgres:postgres@localhost:6432/aws_sdlc_containers
LOCAL_API_BASE_URL     ?= http://127.0.0.1:8000
TF_STATE_BUCKET        ?= $(STACK_NAME)-tfstate-$(ACCOUNT_ID)
ROOT_DOMAIN            ?=
PRIMARY_EDGE_TOKEN_SECRET ?= $(STACK_NAME)/edge-token
TF_PLATFORM_STATE_KEY  ?= $(STACK_NAME)/platform.tfstate
TF_APP_STATE_KEY       ?= $(STACK_NAME)/app.tfstate
TF_PLATFORM_VARS_FILE  := stack.tfvars
TF_APP_VARS_FILE       := stack.tfvars
PRIMARY_EDGE_SERVICE   ?= $(shell python3 -m scripts.platform.workload_metadata primary-edge-contract 2>/dev/null | jq -r '.repository')
SERVICE_NAME           ?= $(PRIMARY_EDGE_SERVICE)
LOOKBACK_MINUTES       ?= 60
RELEASE_EVENTS_DIR     ?=
INCIDENT_EVIDENCE_DIR  ?= /tmp/aws-sdlc-containers-incident-evidence
RELEASE_EVIDENCE_DIR   ?= /tmp/aws-sdlc-containers-release-evidence
GH_RUN_ID              ?=
IMAGE_TAG              ?= sha-$(shell git rev-parse HEAD 2>/dev/null)
PLAN_RUN_ID            ?= <infra-plan-run-id>
TARGET_WORKLOAD        ?= all
SCHEMA_PHASE           ?= expand
SWITCH_STEP            ?= auto-detect

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-36s %s\n", $$1, $$2}'

# ── Local dev ─────────────────────────────────────────────────────────────────

.PHONY: dev
dev: ## Start local Postgres + PgBouncer
	docker compose up -d --remove-orphans db pgbouncer
	docker compose ps db pgbouncer

.PHONY: observability
observability: ## Start local Prometheus + Loki + Promtail + Grafana
	docker compose --profile observability up -d --remove-orphans prometheus loki tempo promtail grafana
	docker compose --profile observability ps prometheus loki tempo promtail grafana

.PHONY: local-up
local-up: ## Build/start local API + Prometheus + Loki + Promtail + Grafana
	docker compose build api
	OTEL_TRACES_ENABLED=true docker compose --profile observability up -d --remove-orphans db pgbouncer api prometheus loki tempo promtail grafana
	docker compose --profile observability ps db pgbouncer api prometheus loki tempo promtail grafana

.PHONY: dapr-up
dapr-up: ## Build/start local Dapr event consumer runtime with Redis pub/sub
	docker compose build event-consumer
	docker compose --profile dapr up -d --remove-orphans db redis event-consumer event-consumer-dapr
	docker compose --profile dapr ps db redis event-consumer event-consumer-dapr

.PHONY: dapr-smoke
dapr-smoke: ## Publish a local Dapr event and verify the consumer records it
	uv run python scripts/platform/local_dapr_smoke.py

.PHONY: api-smoke
api-smoke: ## Verify local API health, readiness, and Prometheus metrics
	@printf "Checking /health... "
	@curl --fail --silent --show-error --retry 20 --retry-delay 2 --retry-connrefused --retry-all-errors "$(LOCAL_API_BASE_URL)/health"
	@printf "\nChecking /ready... "
	@curl --fail --silent --show-error --retry 20 --retry-delay 2 --retry-connrefused --retry-all-errors "$(LOCAL_API_BASE_URL)/ready"
	@printf "\n"
	@printf "Checking /metrics... "
	@curl --fail --silent --show-error --retry 20 --retry-delay 2 --retry-connrefused --retry-all-errors "$(LOCAL_API_BASE_URL)/metrics" | grep -q 'http_requests_total'
	@printf "ok\n"

.PHONY: open-dataset-pipeline
open-dataset-pipeline: ## Run the local-only open dataset workload pipeline
	docker compose build open-dataset-pipeline
	docker compose --profile data run --rm --remove-orphans open-dataset-pipeline

.PHONY: local-down
local-down: ## Stop local API and observability services without deleting volumes
	docker compose --profile observability --profile dapr --profile data stop api prometheus loki tempo promtail grafana event-consumer event-consumer-dapr redis open-dataset-pipeline

.PHONY: local-reset
local-reset: ## Stop all local services and delete Compose volumes
	docker compose --profile observability --profile tools --profile migration --profile data --profile dapr down -v --remove-orphans

.PHONY: observability-stop
observability-stop: ## Stop local observability services
	docker compose --profile observability stop prometheus loki tempo promtail grafana

.PHONY: migrate
migrate: ## Run Liquibase migrations against local DB
	docker compose --profile migration run --rm --remove-orphans liquibase update

.PHONY: seed
seed: ## Seed local DB with test data
	DATABASE_URL="$(or $(DATABASE_URL),$(LOCAL_DATABASE_URL))" uv run python scripts/data/seed_data.py

.PHONY: data-export
data-export: ## Run local data export job into the data_exports Docker volume
	docker compose --profile data run --rm --remove-orphans data-export-job

.PHONY: data-artifacts-list
data-artifacts-list: ## List local data-export and open-dataset artifacts
	docker compose --profile data run --rm --remove-orphans --entrypoint sh open-dataset-pipeline -c 'find /exports -mindepth 1 -maxdepth 6 -type f -print | sort || true'

.PHONY: data-artifacts-shell
data-artifacts-shell: ## Open a shell with the local data artifact volume mounted
	docker compose --profile data run --rm --remove-orphans --entrypoint sh open-dataset-pipeline

.PHONY: data-artifacts-clean
data-artifacts-clean: ## Delete files from the local data_exports Docker volume
	docker compose --profile data run --rm --remove-orphans --entrypoint sh open-dataset-pipeline -c 'find /exports -mindepth 1 -delete'

.PHONY: test
test: ## Run test suite (requires local services and app running)
	uv run pytest tests/ -v

.PHONY: runtime-conformance
runtime-conformance: ## Build/run workload containers against the portable runtime contract
	uv run pytest tests/runtime -v --run-runtime-conformance

.PHONY: platform-toolkit-validate-local
platform-toolkit-validate-local: ## Validate local startup, API, Dapr, jobs, and runtime conformance
	@printf "\n==> Starting local database and PgBouncer\n"
	@$(MAKE) dev
	@printf "\n==> Applying local migrations\n"
	@$(MAKE) migrate
	@printf "\n==> Seeding local data\n"
	@$(MAKE) seed
	@printf "\n==> Starting API and local observability\n"
	@$(MAKE) local-up
	@printf "\n==> Starting Dapr event consumer runtime\n"
	@$(MAKE) dapr-up
	@printf "\n==> Verifying API health, readiness, and metrics\n"
	@$(MAKE) api-smoke
	@printf "\n==> Verifying local Dapr publish and consume path\n"
	@$(MAKE) dapr-smoke
	@printf "\n==> Running local data export job\n"
	@$(MAKE) data-export
	@printf "\n==> Running local open dataset pipeline\n"
	@$(MAKE) open-dataset-pipeline
	@printf "\n==> Running portable runtime conformance\n"
	@$(MAKE) runtime-conformance

# ── Lint & format ─────────────────────────────────────────────────────────────

.PHONY: lint
lint: secret-scan dependency-audit lint-app lint-scripts lint-docs lint-workflows lint-dockerfiles lint-policy lint-infra ## Run all linters

.PHONY: lint-app
lint-app: ## Lint and type-check Python
	uv run ruff check apps/ examples/ packages/ tests/ scripts/
	uv run pyright

.PHONY: lint-scripts
lint-scripts: ## Syntax-check shell scripts
	find scripts -name '*.sh' -print0 | xargs -0 bash -n

.PHONY: lint-docs
lint-docs: ## Check Markdown links
	@if command -v lychee >/dev/null 2>&1; then \
		lychee README.md 'docs/**/*.md'; \
	else \
		docker run --rm \
			-v "$(CURDIR):/repo" \
			-w /repo \
			lycheeverse/lychee:latest@sha256:64bdc8e45d47634ca6a40f29ae48f1916fb7901ffe0eb929e1229590aba27668 \
			README.md 'docs/**/*.md'; \
	fi

.PHONY: lint-workflows
lint-workflows: ## Lint GitHub workflows
	@if command -v actionlint >/dev/null 2>&1; then \
		actionlint; \
	else \
		docker run --rm \
			-v "$(CURDIR):/repo" \
			-w /repo \
			rhysd/actionlint:1.7.12@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667; \
	fi

.PHONY: lint-dockerfiles
lint-dockerfiles: ## Lint Dockerfiles
	@if command -v hadolint >/dev/null 2>&1; then \
		hadolint db/Dockerfile db/pgbouncer/Dockerfile platform/workload.Dockerfile; \
	else \
		docker run --rm \
			-v "$(CURDIR):/repo" \
			-w /repo \
			hadolint/hadolint:v2.14.0-debian@sha256:158cd0184dcaa18bd8ec20b61f4c1cabdf8b32a592d062f57bdcb8e4c1d312e2 \
			hadolint db/Dockerfile db/pgbouncer/Dockerfile platform/workload.Dockerfile; \
	fi

.PHONY: lint-policy
lint-policy: ## Check repo policy with OPA/Conftest
	@if command -v conftest >/dev/null 2>&1; then \
		conftest test --policy platform/concerns/policy/conftest .github/workflows/*.yml platform/workloads.json platform/runtime-conformance.json platform/platform-inventory.json; \
	else \
		docker run --rm \
			-v "$(CURDIR):/project" \
			-w /project \
			openpolicyagent/conftest:v0.64.0 \
			test --policy platform/concerns/policy/conftest .github/workflows/*.yml platform/workloads.json platform/runtime-conformance.json platform/platform-inventory.json; \
	fi

.PHONY: secret-scan
secret-scan: ## Scan repository for committed secrets
	@if command -v gitleaks >/dev/null 2>&1; then \
		gitleaks dir . --redact --no-banner; \
	else \
		docker run --rm \
			-v "$(CURDIR):/repo" \
			zricethezav/gitleaks:v8.30.1 \
			dir /repo --redact --no-banner; \
	fi

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
	uv run ruff format apps/ examples/ packages/ tests/ scripts/
	terraform fmt -recursive infra/

.PHONY: pre-commit
pre-commit: ## Install and run pre-commit hooks
	pre-commit install
	pre-commit run --all-files

.PHONY: platform-toolkit-validate-cloud
platform-toolkit-validate-cloud: ## Run safe cloud readiness checks without mutating AWS
	@printf "\n==> Linting GitHub workflow shape\n"
	@$(MAKE) lint-workflows
	@printf "\n==> Checking platform policy\n"
	@$(MAKE) lint-policy
	@printf "\n==> Running contract and operator-script tests\n"
	@uv run pytest tests/contracts tests/scripts -v

.PHONY: workflow-dry-run-commands
workflow-dry-run-commands: ## Print safe GitHub workflow dry-run dispatch commands
	@printf "Use these after pushing the reviewed branch to the default branch.\n"
	@printf "IMAGE_TAG defaults to %s; override it with IMAGE_TAG=sha-<commit>.\n\n" "$(IMAGE_TAG)"
	@printf "gh workflow run app-deploy.yml --ref main -f image_tag=%s -f confirm_deploy=dry-run -f dry_run=true\n" "$(IMAGE_TAG)"
	@printf "gh workflow run data-support-deploy.yml --ref main -f image_tag=%s -f target_workload=%s -f confirm_data_support_deploy=dry-run -f dry_run=true\n" "$(IMAGE_TAG)" "$(TARGET_WORKLOAD)"
	@printf "gh workflow run data-schema-apply.yml --ref main -f image_tag=%s -f schema_phase=%s -f confirm_schema_apply=dry-run -f dry_run=true\n" "$(IMAGE_TAG)" "$(SCHEMA_PHASE)"
	@printf "gh workflow run data-runtime-switch.yml --ref main -f switch_step=%s -f confirm_switch=dry-run -f dry_run=true\n" "$(SWITCH_STEP)"
	@printf "gh workflow run data-backfill.yml --ref main -f image_tag=%s -f confirm_backfill=dry-run -f dry_run=true\n" "$(IMAGE_TAG)"
	@printf "gh workflow run infra-apply.yml --ref main -f plan_run_id=%s -f confirm_apply=dry-run -f dry_run=true\n" "$(PLAN_RUN_ID)"

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
		-backend-config="bucket=$(TF_STATE_BUCKET)" \
		-backend-config="key=$(TF_PLATFORM_STATE_KEY)" \
		-backend-config="region=$(AWS_REGION)" \
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
		-backend-config="bucket=$(TF_STATE_BUCKET)" \
		-backend-config="key=$(TF_APP_STATE_KEY)" \
		-backend-config="region=$(AWS_REGION)" \
		-reconfigure

.PHONY: infra-app-plan
infra-app-plan: infra-app-init ## Terraform plan — app-owned root
	cd infra/app && terraform plan \
		-var-file=$(TF_APP_VARS_FILE) \
		-var="platform_state_bucket=$(TF_STATE_BUCKET)" \
		-var="platform_state_key=$(TF_PLATFORM_STATE_KEY)"

.PHONY: infra-app-apply
infra-app-apply: infra-app-init ## Terraform apply — app-owned root
	cd infra/app && terraform apply \
		-var-file=$(TF_APP_VARS_FILE) \
		-var="platform_state_bucket=$(TF_STATE_BUCKET)" \
		-var="platform_state_key=$(TF_PLATFORM_STATE_KEY)"

.PHONY: infra-plan
infra-plan: infra-platform-plan infra-app-plan ## Terraform plan — platform then app roots

.PHONY: infra-apply
infra-apply: infra-platform-apply infra-app-apply ## Terraform apply — platform then app roots

# ── App — deploy ──────────────────────────────────────────────────────────────

.PHONY: app-deploy
app-deploy: ## Force new deployment of the declared primary edge ECS service
	aws ecs update-service \
		--cluster $(STACK_NAME) \
		--service $(PRIMARY_EDGE_SERVICE) \
		--task-definition $(STACK_NAME) \
		--force-new-deployment \
		--region $(AWS_REGION) \
		--query 'service.taskDefinition' \
		--output text

.PHONY: post-deploy-verify
post-deploy-verify: ## Verify deployed app readiness, metrics, modes, and ECS image
	@TOKEN="$${TOKEN:-$$(aws secretsmanager get-secret-value \
		--secret-id $(PRIMARY_EDGE_TOKEN_SECRET) \
		--region $(AWS_REGION) \
		--query SecretString --output text)}" \
	BASE_URL="$${BASE_URL:-https://api.$(ROOT_DOMAIN)}" \
	ECS_CLUSTER="$${ECS_CLUSTER:-$(STACK_NAME)}" \
	ECS_SERVICE="$${ECS_SERVICE:-$(PRIMARY_EDGE_SERVICE)}" \
	EXPECTED_TASK_FAMILY="$${EXPECTED_TASK_FAMILY:-$(STACK_NAME)}" \
	uv run python -m scripts.release.verify_post_deploy

.PHONY: observability-delivery-verify
observability-delivery-verify: ## Verify CloudWatch/Loki log delivery inventory and freshness
	@AWS_REGION="$(AWS_REGION)" \
	STACK_NAME="$(STACK_NAME)" \
	uv run python scripts/observability/verify_observability_delivery.py

.PHONY: release-event-delivery-verify
release-event-delivery-verify: ## Verify release-event push/query round-trip through Loki
	@AWS_REGION="$(AWS_REGION)" \
	STACK_NAME="$(STACK_NAME)" \
	uv run python scripts/observability/verify_release_event_loki_delivery.py

.PHONY: release-evidence-runs
release-evidence-runs: ## List recent cloud-changing GitHub workflow runs that emit release evidence
	@printf "RUN_ID\tWORKFLOW\tBRANCH\tSTATUS\tCONCLUSION\tCREATED_AT\tTITLE\tURL\n"
	gh run list \
		--limit 50 \
		--json databaseId,workflowName,displayTitle,headBranch,status,conclusion,createdAt,url \
		--jq '.[] | select(.workflowName as $name | ["App Build", "App Deploy", "Data Support Deploy", "Data Runtime Switch", "Data Schema Apply", "Data Backfill", "Infra Apply"] | index($name)) | [.databaseId, .workflowName, .headBranch, .status, (.conclusion // "-"), .createdAt, .displayTitle, .url] | @tsv'

.PHONY: release-evidence-download
release-evidence-download: ## Download GitHub release-evidence-* artifacts for GH_RUN_ID into $(RELEASE_EVIDENCE_DIR)/$(GH_RUN_ID)
	@[ -n "$(GH_RUN_ID)" ] || (echo "Set GH_RUN_ID=<workflow-run-id>" >&2; exit 1)
	@mkdir -p "$(RELEASE_EVIDENCE_DIR)/$(GH_RUN_ID)"
	gh run download "$(GH_RUN_ID)" \
		--pattern 'release-evidence-*' \
		--dir "$(RELEASE_EVIDENCE_DIR)/$(GH_RUN_ID)"

.PHONY: workload-capability-matrix
workload-capability-matrix: ## Print the declared workload capability matrix from platform/workloads.json
	python3 -m scripts.platform.workload_metadata capability-matrix

.PHONY: workload-use-case-matrix
workload-use-case-matrix: ## Print the declared workload use-case matrix from platform/workloads.json
	python3 -m scripts.platform.workload_metadata use-case-matrix

.PHONY: capability-implementation-matrix
capability-implementation-matrix: ## Print the current runtime capability-to-implementation matrix
	python3 -m scripts.platform.workload_metadata implementation-matrix

.PHONY: adapter-seam-matrix
adapter-seam-matrix: ## Print contract-to-adapter-to-runtime seams for portable capabilities
	python3 -m scripts.platform.workload_metadata adapter-seam-matrix

.PHONY: platform-inventory-json
platform-inventory-json: ## Print machine-readable platform inventory for workloads, runtime seams, and adapter seams
	python3 -m scripts.platform.workload_metadata inventory-json

.PHONY: observability-cloud-traffic
observability-cloud-traffic: ## Generate live API traffic for Grafana/CloudWatch observation
	@AWS_REGION="$(AWS_REGION)" \
	ROOT_DOMAIN="$(ROOT_DOMAIN)" \
	uv run python scripts/observability/generate_cloud_traffic.py

.PHONY: incident-evidence
incident-evidence: ## Build portable Markdown/JSON incident evidence bundle
	@AWS_REGION="$(AWS_REGION)" \
	STACK_NAME="$(STACK_NAME)" \
	ROOT_DOMAIN="$(ROOT_DOMAIN)" \
	RELEASE_EVENTS_DIR="$(RELEASE_EVENTS_DIR)" \
	uv run python scripts/observability/incident_evidence_bundle.py \
		--service-name "$(SERVICE_NAME)" \
		--lookback-minutes "$(LOOKBACK_MINUTES)" \
		--output-dir "$(INCIDENT_EVIDENCE_DIR)"

# ── DB access — no bastion needed ─────────────────────────────────────────────
#
# Remote DB access targets delegate to shell scripts under scripts/ to avoid
# Make's quoting limitations with JMESPath backtick filters.
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
db-seed: ## Seed DB — run make db-tunnel first for remote DBs  (SEED_NUM_CUSTOMERS=1000, SEED_NUM_ORDERS=10000)
	SEED_NUM_CUSTOMERS=$(SEED_NUM_CUSTOMERS) SEED_NUM_ORDERS=$(SEED_NUM_ORDERS) \
		uv run python scripts/data/seed_data.py

# ── API smoke query ───────────────────────────────────────────────────────────
#
# Fetches a single order from the live primary edge and prints the full
# response or a single field. Requires the single HTTPS entrypoint and
# bearer-token auth.
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
			--secret-id $(PRIMARY_EDGE_TOKEN_SECRET) \
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
