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
#   make platform-toolkit-smoke-local
#                             — fast local confidence check
#   make platform-toolkit-validate-local
#                             — prove the local workload journey end to end
#   make test                — run test suite
#   make runtime-conformance — build/run workload images against platform contract
#   make workload-readiness  — show paved-road coverage for each workload
#   make workload-readiness-check
#                             — fail on missing paved-road workload coverage
#   make workload-addition-report
#                             — show conventional files for workload additions
#   make workload-fit-init   — generate a draft externally operated workload
#   make workload-fit-check  — evaluate a draft externally operated workload
#   make workload-local-proof-plan
#                             — plan local proof work for a passing candidate
#   make runtime-defaults     — show blessed defaults for active runtimes
#   make candidate-capability-matrix
#                             — show candidate-only enterprise runtime choices
#   make capability-proof-local
#                             — summarize local runtime capability evidence
#   make capability-proof-local-live
#                             — run isolated live local runtime capability drill
#   make capability-proof-cloud
#                             — summarize AWS runtime wiring evidence
#   make enterprise-runtime-fit-check
#                             — show candidate enterprise promotion gaps
#   make platform-toolkit-validate-cloud
#                             — run safe cloud readiness checks without mutating AWS
#   make platform-doctor      — check human workstation readiness
#   make lint                — run all linters (app + infra)
#   make fmt                 — auto-format everything
#
#   make bootstrap           — one-time AWS account setup, idempotent
#
#   make infra-platform-plan — terraform plan for platform/bootstrap root
#   make infra-app-plan      — terraform plan for app-owned root
#   make infra-validate-local
#                             — terraform fmt/init/validate without remote backend
#
#   make app-deploy          — force new ECS deployment
#   make operational-snapshot
#                             — emit local operational readiness snapshot
#   make integration-check    — run configured local HTTP integration checks
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
PRIMARY_EDGE_HOSTNAME_LABEL ?= $(shell python3 -m scripts.platform.workload_metadata primary-edge-contract 2>/dev/null | jq -r '.hostname_label')
SERVICE_NAME           ?= $(PRIMARY_EDGE_SERVICE)
LOOKBACK_MINUTES       ?= 60
INCIDENT_EVIDENCE_DIR  ?= /tmp/aws-sdlc-containers-incident-evidence
RELEASE_EVIDENCE_DIR   ?= /tmp/aws-sdlc-containers-release-evidence
GH_RUN_ID              ?=
RELEASE_EVENTS_DIR     ?= $(if $(GH_RUN_ID),$(RELEASE_EVIDENCE_DIR)/$(GH_RUN_ID),)
BACKFILL_MAX_BATCHES   ?= 1
IMAGE_TAG              ?=
PLAN_RUN_ID            ?= <infra-plan-run-id>
TARGET_WORKLOAD        ?= all
SCHEMA_PHASE           ?= expand
SWITCH_STEP            ?= auto-detect
INTEGRATION_CHECK_TARGETS ?=
INTEGRATION_CHECK_TIMEOUT_SECONDS ?= 5

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
	@metrics=$$(curl --fail --silent --show-error --retry 20 --retry-delay 2 --retry-connrefused --retry-all-errors "$(LOCAL_API_BASE_URL)/metrics"); \
		printf "%s" "$$metrics" | grep -q 'http_requests_total'; \
		printf "%s" "$$metrics" | grep -q 'workload_info{workload="api"'
	@printf "ok\n"

.PHONY: open-dataset-pipeline
open-dataset-pipeline: ## Run the local-only open dataset workload pipeline
	docker compose build open-dataset-pipeline
	docker compose --profile data run --rm --remove-orphans open-dataset-pipeline

.PHONY: local-down
local-down: ## Stop local API and observability services without deleting volumes
	docker compose --profile observability --profile dapr --profile data --profile ops stop api prometheus loki tempo promtail grafana event-consumer event-consumer-dapr redis open-dataset-pipeline operational-snapshot-job integration-check-job

.PHONY: local-reset
local-reset: ## Stop all local services and delete Compose volumes
	docker compose --profile observability --profile tools --profile migration --profile data --profile dapr --profile ops down -v --remove-orphans

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

.PHONY: operational-snapshot
operational-snapshot: ## Run local read-only operational readiness snapshot
	docker compose --profile ops run --rm --remove-orphans operational-snapshot-job

.PHONY: integration-check
integration-check: ## Run configured local HTTP integration checks
	@[ -n "$(INTEGRATION_CHECK_TARGETS)" ] || (echo "Set INTEGRATION_CHECK_TARGETS, for example: INTEGRATION_CHECK_TARGETS=api=http://api:8000/health make integration-check" >&2; exit 1)
	INTEGRATION_CHECK_TARGETS="$(INTEGRATION_CHECK_TARGETS)" INTEGRATION_CHECK_TIMEOUT_SECONDS="$(INTEGRATION_CHECK_TIMEOUT_SECONDS)" \
		docker compose --profile ops run --rm --remove-orphans integration-check-job

.PHONY: backfill-once
backfill-once: ## Run one bounded local backfill batch
	docker compose run --rm --remove-orphans -e BACKFILL_MAX_BATCHES=$(BACKFILL_MAX_BATCHES) backfill-worker

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

.PHONY: workload-addition-report
workload-addition-report: ## Show conventional files to check when adding workloads
	python3 scripts/platform/workload_readiness.py --addition-report

.PHONY: platform-doctor
platform-doctor: ## Check local workstation readiness for the delivery toolkit
	python3 scripts/platform/doctor.py

.PHONY: platform-doctor-cloud
platform-doctor-cloud: ## Check local plus cloud/operator readiness for the delivery toolkit
	python3 scripts/platform/doctor.py --cloud

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
	@printf "\n==> Running local operational snapshot job\n"
	@$(MAKE) operational-snapshot
	@printf "\n==> Running local integration check job\n"
	@INTEGRATION_CHECK_TARGETS="api=http://api:8000/health" $(MAKE) integration-check
	@printf "\n==> Running local open dataset pipeline\n"
	@$(MAKE) open-dataset-pipeline
	@printf "\n==> Running portable runtime conformance\n"
	@$(MAKE) runtime-conformance

.PHONY: platform-toolkit-smoke-local
platform-toolkit-smoke-local: ## Fast local smoke: API, Dapr, and one backfill batch
	@printf "\n==> Starting local app and Dapr surfaces\n"
	@$(MAKE) dev
	@$(MAKE) migrate
	@$(MAKE) local-up
	@$(MAKE) dapr-up
	@printf "\n==> Verifying API and Dapr\n"
	@$(MAKE) api-smoke
	@$(MAKE) dapr-smoke
	@printf "\n==> Running one bounded backfill batch\n"
	@$(MAKE) backfill-once

# ── Lint & format ─────────────────────────────────────────────────────────────

.PHONY: lint
lint: secret-scan dependency-audit lint-app lint-scripts lint-docs lint-workflows lint-dockerfiles lint-policy workload-readiness-check lint-infra ## Run all linters

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

.PHONY: infra-validate-local
infra-validate-local: ## Validate Terraform syntax locally without backend or cloud mutation
	python3 scripts/ci/terraform_readiness.py

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
	@printf "\n==> Checking workload paved-road readiness\n"
	@$(MAKE) workload-readiness-check
	@printf "\n==> Linting GitHub workflow shape\n"
	@$(MAKE) lint-workflows
	@printf "\n==> Checking platform policy\n"
	@$(MAKE) lint-policy
	@printf "\n==> Validating generated workflow dry-run commands\n"
	@$(MAKE) workflow-dry-run-validate
	@printf "\n==> Running contract and operator-script tests\n"
	@uv run pytest tests/contracts tests/scripts -v

.PHONY: workflow-dry-run-commands
workflow-dry-run-commands: ## Print safe GitHub workflow dry-run dispatch commands
	@IMAGE_TAG="$(IMAGE_TAG)" PLAN_RUN_ID="$(PLAN_RUN_ID)" TARGET_WORKLOAD="$(TARGET_WORKLOAD)" SCHEMA_PHASE="$(SCHEMA_PHASE)" SWITCH_STEP="$(SWITCH_STEP)" \
		python3 scripts/ci/workflow_dry_run_commands.py commands

.PHONY: workflow-dry-run-validate
workflow-dry-run-validate: ## Validate dry-run commands against local workflow input names
	python3 scripts/ci/workflow_dry_run_commands.py validate-local

.PHONY: workflow-dry-run-validate-gh
workflow-dry-run-validate-gh: workflow-dry-run-validate ## Check GitHub CLI auth before dispatching workflow dry runs
	gh auth status
	gh workflow list --all --limit 50

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
	BASE_URL="$${BASE_URL:-https://$(PRIMARY_EDGE_HOSTNAME_LABEL).$(ROOT_DOMAIN)}" \
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
release-evidence-runs: ## List recent downloadable release evidence and operator payload artifacts
	@printf "RUN_ID\tBRANCH\tSHA\tLATEST_ARTIFACT_AT\tRELEASE_EVIDENCE\tOPERATOR_PAYLOAD\tARTIFACTS\n"
	@gh api 'repos/:owner/:repo/actions/artifacts?per_page=100' \
		--jq '[.artifacts[] | select((.expired | not) and (.name | test("^(release-evidence|operator-payload)-")))] | group_by(.workflow_run.id) | map({run_id: .[0].workflow_run.id, branch: .[0].workflow_run.head_branch, sha: .[0].workflow_run.head_sha[0:12], latest_artifact_at: (map(.created_at) | max), release_evidence: (map(select(.name | startswith("release-evidence-"))) | length), operator_payload: (map(select(.name | startswith("operator-payload-"))) | length), artifacts: length}) | sort_by(.latest_artifact_at) | reverse[] | [.run_id, .branch, .sha, .latest_artifact_at, .release_evidence, .operator_payload, .artifacts] | @tsv'

.PHONY: release-evidence-download
release-evidence-download: ## Download GitHub release-evidence-* artifacts for GH_RUN_ID into $(RELEASE_EVIDENCE_DIR)/$(GH_RUN_ID)
	@[ -n "$(GH_RUN_ID)" ] || (echo "Set GH_RUN_ID=<workflow-run-id>" >&2; exit 1)
	@mkdir -p "$(RELEASE_EVIDENCE_DIR)/$(GH_RUN_ID)"
	@gh run download "$(GH_RUN_ID)" \
		--pattern 'release-evidence-*' \
		--dir "$(RELEASE_EVIDENCE_DIR)/$(GH_RUN_ID)" || \
		(echo "No release-evidence-* artifact found for GH_RUN_ID=$(GH_RUN_ID)." >&2; \
		 echo "Run 'make release-evidence-runs' and choose a listed RUN_ID with RELEASE_EVIDENCE > 0." >&2; \
		 exit 1)

.PHONY: operator-payload-download
operator-payload-download: ## Download operator-payload-* artifacts for GH_RUN_ID into $(RELEASE_EVIDENCE_DIR)/$(GH_RUN_ID)
	@[ -n "$(GH_RUN_ID)" ] || (echo "Set GH_RUN_ID=<workflow-run-id>" >&2; exit 1)
	@mkdir -p "$(RELEASE_EVIDENCE_DIR)/$(GH_RUN_ID)"
	@gh run download "$(GH_RUN_ID)" \
		--pattern 'operator-payload-*' \
		--dir "$(RELEASE_EVIDENCE_DIR)/$(GH_RUN_ID)" || \
		(echo "No operator-payload-* artifact found for GH_RUN_ID=$(GH_RUN_ID)." >&2; \
		 echo "Run 'make release-evidence-runs' and choose a listed RUN_ID with OPERATOR_PAYLOAD > 0." >&2; \
		 exit 1)

.PHONY: operational-snapshot-dry-run
operational-snapshot-dry-run: ## Dispatch non-destructive Operational Snapshot readiness checks
	gh workflow run operational-snapshot.yml --ref main \
		-f confirm_snapshot=dry-run \
		-f dry_run=true

.PHONY: operational-snapshot-cloud
operational-snapshot-cloud: ## Dispatch the reviewed AWS operational snapshot operator job
	gh workflow run operational-snapshot.yml --ref main \
		-f confirm_snapshot=run-operational-snapshot \
		-f dry_run=false

.PHONY: workload-capability-matrix
workload-capability-matrix: ## Print the declared workload capability matrix from platform/workloads.json
	python3 -m scripts.platform.workload_metadata capability-matrix

.PHONY: workload-use-case-matrix
workload-use-case-matrix: ## Print the declared workload use-case matrix from platform/workloads.json
	python3 -m scripts.platform.workload_metadata use-case-matrix

.PHONY: workload-readiness
workload-readiness: ## Print workload paved-road readiness from contract, workflows, and evidence surfaces
	python3 scripts/platform/workload_readiness.py

.PHONY: workload-readiness-check
workload-readiness-check: ## Fail when declared workloads lack paved-road readiness
	python3 scripts/platform/workload_readiness.py --check

.PHONY: workload-fit-check
workload-fit-check: ## Evaluate a draft externally operated workload before admission
	@[ -n "$(WORKLOAD_CANDIDATE)" ] || (echo "Set WORKLOAD_CANDIDATE=/path/to/workload.json" >&2; exit 1)
	python3 scripts/platform/workload_fit_check.py --candidate "$(WORKLOAD_CANDIDATE)"

.PHONY: workload-fit-init
workload-fit-init: ## Generate a draft externally operated workload candidate
	@[ -n "$(NAME)" ] || (echo "Set NAME=<workload_name>" >&2; exit 1)
	@[ -n "$(KIND)" ] || (echo "Set KIND=service or KIND=job" >&2; exit 1)
	@[ -n "$(CLASS)" ] || (echo "Set CLASS=<operational-class>" >&2; exit 1)
	@[ -n "$(OWNER)" ] || (echo "Set OWNER=<team-name>" >&2; exit 1)
	python3 scripts/platform/workload_fit_init.py --name "$(NAME)" --kind "$(KIND)" --class "$(CLASS)" --owner "$(OWNER)" $(if $(OUTPUT),--output "$(OUTPUT)",)

.PHONY: workload-local-proof-plan
workload-local-proof-plan: ## Plan local proof work for a passing workload candidate
	@[ -n "$(WORKLOAD_CANDIDATE)" ] || (echo "Set WORKLOAD_CANDIDATE=/path/to/workload.json" >&2; exit 1)
	python3 scripts/platform/workload_local_proof_plan.py --candidate "$(WORKLOAD_CANDIDATE)"

.PHONY: capability-implementation-matrix
capability-implementation-matrix: ## Print the current runtime capability-to-implementation matrix
	python3 -m scripts.platform.workload_metadata implementation-matrix

.PHONY: candidate-capability-matrix
candidate-capability-matrix: ## Print candidate-only enterprise runtime capability choices
	python3 -m scripts.platform.workload_metadata candidate-implementation-matrix

.PHONY: capability-proof-local
capability-proof-local: ## Summarize local runtime capability proof evidence
	python3 scripts/platform/capability_proof.py --runtime-target local-compose

.PHONY: capability-proof-local-live
capability-proof-local-live: ## Run isolated live local runtime capability proof
	python3 scripts/platform/capability_live_proof.py

.PHONY: capability-proof-cloud
capability-proof-cloud: ## Summarize AWS runtime wiring proof evidence
	python3 scripts/platform/capability_proof.py --runtime-target aws-ecs

.PHONY: enterprise-runtime-fit-check
enterprise-runtime-fit-check: ## Show candidate enterprise runtime promotion gaps
	python3 scripts/platform/enterprise_runtime_fit_check.py

.PHONY: adapter-seam-matrix
adapter-seam-matrix: ## Print contract-to-adapter-to-runtime seams for portable capabilities
	python3 -m scripts.platform.workload_metadata adapter-seam-matrix

.PHONY: runtime-defaults
runtime-defaults: ## Print blessed defaults for active runtime targets
	python3 -m scripts.platform.workload_metadata runtime-defaults

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
	uv run python -m scripts.observability.incident_evidence_bundle \
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
