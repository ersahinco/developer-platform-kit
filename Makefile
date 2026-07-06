# ─────────────────────────────────────────────────────────────────────────────
# Makefile — local dev, split-root infra, and operator commands
#
# Prerequisites (install once):
#   Recommended: open the repo in its dev container.
#   Native host tooling is optional; keep it aligned with docs/local-development.md.
#
# Usage:
#   make help                — focused command groups
#   make help-local          — first-run and daily local commands
#   make help-proof          — proof ladder and evidence commands
#   make help-cloud          — cloud readiness and deploy commands
#   make help-operator       — day-2 evidence and operator commands
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
LOCAL_KUBERNETES_CLUSTER ?= aws-sdlc-local
LOCAL_KUBERNETES_NAMESPACE ?= aws-sdlc-local
LOCAL_KUBERNETES_TAG ?= local-kubernetes
LOCAL_KUBERNETES_ROLLOUT_TAG ?= local-kubernetes-rollout
LOCAL_KUBERNETES_EVIDENCE_DIR ?= /tmp/aws-sdlc-containers-local-kubernetes-evidence
LOCAL_KUBERNETES_IMAGE_MATRIX := uv run python -m scripts.platform.workload_metadata local-kubernetes-image-matrix
SECURITY_REPORT_DIR    ?= /tmp/aws-sdlc-containers-security
TRIVY_SEVERITY         ?= HIGH,CRITICAL
CONTAINER_SCAN_IMAGE   ?=
DEEPFENCE_IMAGE_NAME   ?= $(CONTAINER_SCAN_IMAGE)
DEEPFENCE_SECRET_SCANNER_IMAGE ?= quay.io/deepfenceio/deepfence_secret_scanner_ce:2.5.8
OWASP_DEPENDENCY_CHECK_IMAGE ?= owasp/dependency-check:12.1.0

define local_kubernetes_build_images
	@set -e; \
	$(LOCAL_KUBERNETES_IMAGE_MATRIX) "$(1)" | jq -r '$(2) | [(.repository + ":" + .tag), .dockerfile, .context, (.build_args.APP_PATH // ""), (.build_args.UV_PACKAGE // ""), (.build_args.WORKLOAD_CMD // "")] | @sh' | while read -r row; do \
		eval "set -- $$row"; \
		if [ -n "$$4" ]; then \
			docker build -f "$$2" -t "$$1" --build-arg "APP_PATH=$$4" --build-arg "UV_PACKAGE=$$5" --build-arg "WORKLOAD_CMD=$$6" "$$3"; \
		else \
			docker build -f "$$2" -t "$$1" "$$3"; \
		fi; \
	done
endef

define local_kubernetes_image_names
$(LOCAL_KUBERNETES_IMAGE_MATRIX) "$(1)" | jq -r '$(2) | .repository + ":" + .tag'
endef

define local_kubernetes_primary_edge_image
$(call local_kubernetes_image_names,$(1),.[] | select(.primary_edge == true))
endef

# ── Help ──────────────────────────────────────────────────────────────────────

HELP_LOCAL_TARGETS := platform-doctor workload-readiness workload-readiness-local dev migrate seed local-app-up local-up api-smoke dapr-up dapr-smoke platform-toolkit-smoke-local platform-toolkit-validate-local local-down local-reset
HELP_PROOF_TARGETS := monorepo-capability-profile monorepo-capability-profile-md monorepo-capability-profile-check workload-admission-check workload-readiness workload-readiness-local workload-readiness-cloud workload-readiness-check runtime-conformance local-compose-live-proof local-kubernetes-contracts local-kubernetes-admission-report local-kubernetes-evidence-drill local-kubernetes-rollout-proof workflow-dry-run-validate
HELP_CLOUD_TARGETS := platform-doctor-cloud platform-toolkit-validate-cloud security-readiness infra-validate-local workflow-dry-run-validate workflow-dry-run-commands workflow-dry-run-validate-gh infra-platform-plan infra-app-plan app-deploy post-deploy-verify release-evidence-runs operational-snapshot-cloud
HELP_OPERATOR_TARGETS := release-evidence-runs release-evidence-download operator-payload-download operational-snapshot operational-snapshot-dry-run operational-snapshot-cloud incident-evidence db-tunnel db-exec db-seed api-get-order observability-delivery-verify release-event-delivery-verify integration-check data-artifacts-list

define print_help_targets
	@awk -v targets="$(strip $(1))" 'BEGIN { count = split(targets, names, " ") } /^[a-zA-Z0-9_-]+:.*## / { target = $$1; sub(/:.*/, "", target); help = $$0; sub(/^[^:]+:.*## /, "", help); help_by_target[target] = help } END { for (i = 1; i <= count; i++) { target = names[i]; if (target in help_by_target) { printf "  %-36s %s\n", target, help_by_target[target] } else { missing = missing " " target } } if (missing != "") { print "Missing documented targets:" missing > "/dev/stderr"; exit 1 } }' $(MAKEFILE_LIST)
endef

.PHONY: help help-local help-proof help-cloud help-operator
help: ## Show focused command groups
	@printf "Start here\n"
	@printf "  %-36s %s\n" "help-local" "First-run and daily local commands"
	@printf "  %-36s %s\n" "help-proof" "Proof ladder and evidence commands"
	@printf "  %-36s %s\n" "help-cloud" "Cloud readiness and deploy commands"
	@printf "  %-36s %s\n" "help-operator" "Day-2 evidence and operator commands"
	@printf "\nRun a focused help target instead of scanning every Make target.\n"

help-local: ## Show first-run and daily local commands
	@printf "Local developer loop\n"
	$(call print_help_targets,$(HELP_LOCAL_TARGETS))

help-proof: ## Show proof ladder and evidence commands
	@printf "Proof and evidence\n"
	$(call print_help_targets,$(HELP_PROOF_TARGETS))

help-cloud: ## Show cloud readiness and deploy commands
	@printf "Cloud readiness and deploy\n"
	$(call print_help_targets,$(HELP_CLOUD_TARGETS))

help-operator: ## Show day-2 evidence and operator commands
	@printf "Operator evidence and day-2\n"
	$(call print_help_targets,$(HELP_OPERATOR_TARGETS))

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

.PHONY: local-app-up
local-app-up: ## Build/start local API without the observability stack
	docker compose build api
	docker compose up -d --remove-orphans db pgbouncer api
	docker compose ps db pgbouncer api

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
runtime-conformance: ## Static proof ladder: build/run workloads against the portable contract
	uv run pytest tests/runtime -v --run-runtime-conformance

.PHONY: platform-doctor
platform-doctor: ## Check local workstation readiness for the delivery toolkit
	uv run python scripts/platform/doctor.py

.PHONY: platform-doctor-cloud
platform-doctor-cloud: ## Check local plus cloud/operator readiness for the delivery toolkit
	uv run python scripts/platform/doctor.py --cloud

.PHONY: platform-toolkit-validate-local
platform-toolkit-validate-local: ## Local Compose proof ladder: validate API, Dapr, jobs, and conformance
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
	@$(MAKE) local-app-up
	@$(MAKE) dapr-up
	@printf "\n==> Verifying API and Dapr\n"
	@$(MAKE) api-smoke
	@$(MAKE) dapr-smoke
	@printf "\n==> Running one bounded backfill batch\n"
	@$(MAKE) backfill-once

.PHONY: _local-kubernetes-doctor
_local-kubernetes-doctor:
	@command -v uv >/dev/null || (echo "uv is required for local-kubernetes" >&2; exit 1)
	@command -v jq >/dev/null || (echo "jq is required for local-kubernetes" >&2; exit 1)
	@command -v docker >/dev/null || (echo "docker is required for local-kubernetes" >&2; exit 1)
	@command -v kind >/dev/null || (echo "kind is required for local-kubernetes" >&2; exit 1)
	@command -v kubectl >/dev/null || (echo "kubectl is required for local-kubernetes" >&2; exit 1)

.PHONY: _local-kubernetes-build
_local-kubernetes-build:
	$(call local_kubernetes_build_images,$(LOCAL_KUBERNETES_TAG),.[])

.PHONY: _local-kubernetes-build-rollout
_local-kubernetes-build-rollout:
	$(call local_kubernetes_build_images,$(LOCAL_KUBERNETES_ROLLOUT_TAG),.[] | select(.primary_edge == true))

.PHONY: _local-kubernetes-up
_local-kubernetes-up:
	@kind get clusters | grep -qx "$(LOCAL_KUBERNETES_CLUSTER)" || kind create cluster --name "$(LOCAL_KUBERNETES_CLUSTER)"
	@set -e; \
	$(call local_kubernetes_image_names,$(LOCAL_KUBERNETES_TAG),.[]) | while read -r image; do \
		kind load docker-image --name "$(LOCAL_KUBERNETES_CLUSTER)" "$$image"; \
	done

.PHONY: _local-kubernetes-apply
_local-kubernetes-apply:
	kubectl delete job liquibase backfill-worker data-export-job operational-snapshot-job integration-check-job -n "$(LOCAL_KUBERNETES_NAMESPACE)" --ignore-not-found
	kubectl apply -k infra/local-kubernetes
	kubectl wait --for=condition=available deployment/db -n "$(LOCAL_KUBERNETES_NAMESPACE)" --timeout=180s
	kubectl wait --for=condition=available deployment/pgbouncer -n "$(LOCAL_KUBERNETES_NAMESPACE)" --timeout=180s
	kubectl wait --for=condition=available deployment/redis -n "$(LOCAL_KUBERNETES_NAMESPACE)" --timeout=180s
	kubectl wait --for=condition=complete job/liquibase -n "$(LOCAL_KUBERNETES_NAMESPACE)" --timeout=180s
	kubectl wait --for=condition=available deployment/api -n "$(LOCAL_KUBERNETES_NAMESPACE)" --timeout=180s
	kubectl wait --for=condition=available deployment/event-consumer -n "$(LOCAL_KUBERNETES_NAMESPACE)" --timeout=180s

.PHONY: _local-kubernetes-smoke
_local-kubernetes-smoke:
	kubectl wait --for=condition=complete job/backfill-worker -n "$(LOCAL_KUBERNETES_NAMESPACE)" --timeout=180s
	kubectl wait --for=condition=complete job/data-export-job -n "$(LOCAL_KUBERNETES_NAMESPACE)" --timeout=180s
	kubectl wait --for=condition=complete job/operational-snapshot-job -n "$(LOCAL_KUBERNETES_NAMESPACE)" --timeout=180s
	kubectl wait --for=condition=complete job/integration-check-job -n "$(LOCAL_KUBERNETES_NAMESPACE)" --timeout=180s
	@set -e; \
		kubectl port-forward -n "$(LOCAL_KUBERNETES_NAMESPACE)" service/api 18080:8000 >/tmp/aws-sdlc-local-kubernetes-port-forward.log 2>&1 & \
		pf_pid=$$!; \
		trap 'kill $$pf_pid >/dev/null 2>&1 || true' EXIT; \
		for attempt in 1 2 3 4 5 6 7 8 9 10; do curl --fail --silent http://127.0.0.1:18080/health >/dev/null && break || sleep 2; done; \
		curl --fail --silent http://127.0.0.1:18080/health >/dev/null; \
		curl --fail --silent http://127.0.0.1:18080/ready >/dev/null; \
		curl --fail --silent http://127.0.0.1:18080/metrics | grep -q 'workload_info{workload="api"'
	kubectl logs -n "$(LOCAL_KUBERNETES_NAMESPACE)" job/backfill-worker | grep -Eq 'backfill_(complete|paused)'
	kubectl logs -n "$(LOCAL_KUBERNETES_NAMESPACE)" job/data-export-job | grep -q data_export_succeeded
	kubectl logs -n "$(LOCAL_KUBERNETES_NAMESPACE)" job/operational-snapshot-job | grep -q operational_snapshot_succeeded
	kubectl logs -n "$(LOCAL_KUBERNETES_NAMESPACE)" job/integration-check-job | grep -q integration_check_succeeded
	$(MAKE) _local-kubernetes-dapr-proof

.PHONY: _local-kubernetes-down
_local-kubernetes-down:
	-kind delete cluster --name "$(LOCAL_KUBERNETES_CLUSTER)"

.PHONY: local-kubernetes-rollout-proof
local-kubernetes-rollout-proof: ## Local Kubernetes proof ladder: API rollout/rollback evidence
	@set -e; \
		trap 'status=$$?; if [ $$status -ne 0 ]; then $(MAKE) _local-kubernetes-evidence-bundle || true; fi; $(MAKE) _local-kubernetes-down; exit $$status' EXIT; \
		$(MAKE) _local-kubernetes-doctor; \
		$(MAKE) _local-kubernetes-build; \
		$(MAKE) _local-kubernetes-build-rollout; \
		$(MAKE) _local-kubernetes-up; \
		primary_edge_image="$$( $(call local_kubernetes_primary_edge_image,$(LOCAL_KUBERNETES_ROLLOUT_TAG)) )"; \
		kind load docker-image --name "$(LOCAL_KUBERNETES_CLUSTER)" "$$primary_edge_image"; \
		$(MAKE) _local-kubernetes-apply; \
		uv run python scripts/platform/local_kubernetes_proof.py --namespace "$(LOCAL_KUBERNETES_NAMESPACE)" --output-dir "$(LOCAL_KUBERNETES_EVIDENCE_DIR)" rollout-proof --candidate-image "$$primary_edge_image"; \
		$(MAKE) _local-kubernetes-evidence-bundle

.PHONY: _local-kubernetes-dapr-proof
_local-kubernetes-dapr-proof:
	uv run python scripts/platform/local_kubernetes_proof.py --namespace "$(LOCAL_KUBERNETES_NAMESPACE)" --output-dir "$(LOCAL_KUBERNETES_EVIDENCE_DIR)" dapr-eventing-proof

.PHONY: local-kubernetes-evidence-drill
local-kubernetes-evidence-drill: ## Local Kubernetes proof ladder: runtime evidence drill
	@set -e; \
		trap 'status=$$?; if [ $$status -ne 0 ]; then $(MAKE) _local-kubernetes-evidence-bundle || true; fi; $(MAKE) _local-kubernetes-down; exit $$status' EXIT; \
		$(MAKE) _local-kubernetes-doctor; \
		$(MAKE) _local-kubernetes-build; \
		$(MAKE) _local-kubernetes-up; \
		$(MAKE) _local-kubernetes-apply; \
		$(MAKE) _local-kubernetes-smoke; \
		$(MAKE) _local-kubernetes-evidence-bundle

.PHONY: _local-kubernetes-evidence-bundle
_local-kubernetes-evidence-bundle:
	uv run python scripts/platform/local_kubernetes_proof.py --namespace "$(LOCAL_KUBERNETES_NAMESPACE)" --output-dir "$(LOCAL_KUBERNETES_EVIDENCE_DIR)" evidence-bundle

.PHONY: local-kubernetes-admission-report
local-kubernetes-admission-report: ## Local Kubernetes proof ladder: explain workload readiness gaps
	uv run python scripts/platform/local_kubernetes_proof.py --namespace "$(LOCAL_KUBERNETES_NAMESPACE)" admission-report

.PHONY: local-kubernetes-contracts
local-kubernetes-contracts: ## Run static local Kubernetes contract checks
	uv run pytest tests/contracts/test_local_kubernetes_contract.py tests/contracts/test_runtime_defaults_contract.py tests/contracts/test_non_goal_boundary_contract.py -q

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
		conftest test --policy platform/concerns/policy/conftest .github/workflows/*.yml platform/workloads.json platform/runtime-conformance.json platform/platform-inventory.json platform/runtime-defaults.json; \
	else \
		docker run --rm \
			-v "$(CURDIR):/project" \
			-w /project \
			openpolicyagent/conftest:v0.64.0 \
			test --policy platform/concerns/policy/conftest .github/workflows/*.yml platform/workloads.json platform/runtime-conformance.json platform/platform-inventory.json platform/runtime-defaults.json; \
	fi

.PHONY: secret-scan
secret-scan: secret-scan-gitleaks ## Scan repository for committed secrets

.PHONY: secret-scan-gitleaks
secret-scan-gitleaks: ## Scan repository for committed secrets with Gitleaks
	@if command -v gitleaks >/dev/null 2>&1; then \
		gitleaks dir . --redact --no-banner; \
	else \
		docker run --rm \
			-v "$(CURDIR):/repo" \
			zricethezav/gitleaks:v8.30.1 \
			dir /repo --redact --no-banner; \
	fi

.PHONY: secret-scan-deepfence
secret-scan-deepfence: ## Scan a built container image for secrets with Deepfence SecretScanner
	@if [ -z "$(DEEPFENCE_IMAGE_NAME)" ]; then \
		echo "Set DEEPFENCE_IMAGE_NAME or CONTAINER_SCAN_IMAGE to scan image secrets with Deepfence SecretScanner."; \
	else \
		mkdir -p "$(SECURITY_REPORT_DIR)"; \
		docker run -i --rm --name deepfence-secretscanner \
			-v /var/run/docker.sock:/var/run/docker.sock \
			$(DEEPFENCE_SECRET_SCANNER_IMAGE) \
			--image-name "$(DEEPFENCE_IMAGE_NAME)" \
			--output json > "$(SECURITY_REPORT_DIR)/deepfence-secrets.json"; \
	fi

.PHONY: dependency-audit
dependency-audit: ## Audit uv-locked Python dependencies for known vulnerabilities
	@tmpfile=$$(mktemp); \
	trap 'rm -f "$$tmpfile"' EXIT; \
	uv --quiet export --format requirements.txt --all-packages --all-groups --no-emit-project --no-emit-workspace --frozen --output-file "$$tmpfile"; \
	uv run pip-audit -r "$$tmpfile" --disable-pip --require-hashes --progress-spinner off --desc off --aliases off

.PHONY: dependency-audit-owasp
dependency-audit-owasp: ## Audit dependency manifests with OWASP Dependency-Check
	@mkdir -p "$(SECURITY_REPORT_DIR)/dependency-check"
	@if command -v dependency-check.sh >/dev/null 2>&1; then \
		dependency-check.sh \
			--project "$(STACK_NAME)" \
			--scan "$(CURDIR)" \
			--out "$(SECURITY_REPORT_DIR)/dependency-check" \
			--format HTML \
			--format JSON \
			--failOnCVSS 7 \
			--exclude "**/.git/**" \
			--exclude "**/.venv/**"; \
	else \
		docker run --rm \
			-v "$(CURDIR):/src" \
			-v "$(SECURITY_REPORT_DIR)/dependency-check:/report" \
			$(OWASP_DEPENDENCY_CHECK_IMAGE) \
			--project "$(STACK_NAME)" \
			--scan /src \
			--out /report \
			--format HTML \
			--format JSON \
			--failOnCVSS 7 \
			--exclude "**/.git/**" \
			--exclude "**/.venv/**"; \
	fi

.PHONY: container-config-scan
container-config-scan: ## Scan repository container/IaC config with Trivy
	@if command -v trivy >/dev/null 2>&1; then \
		trivy fs \
			--scanners vuln,secret,misconfig \
			--severity "$(TRIVY_SEVERITY)" \
			--exit-code 1 \
			--ignore-unfixed \
			--skip-dirs .git \
			--skip-dirs .venv \
			.; \
	else \
		docker run --rm \
			-v "$(CURDIR):/repo" \
			-v "$$HOME/.cache/trivy:/root/.cache/trivy" \
			ghcr.io/aquasecurity/trivy:0.70.0@sha256:be1190afcb28352bfddc4ddeb71470835d16462af68d310f9f4bca710961a41e \
			fs \
			--scanners vuln,secret,misconfig \
			--severity "$(TRIVY_SEVERITY)" \
			--exit-code 1 \
			--ignore-unfixed \
			--skip-dirs .git \
			--skip-dirs .venv \
			/repo; \
	fi

.PHONY: container-image-scan
container-image-scan: ## Scan a built container image with Trivy
	@if [ -z "$(CONTAINER_SCAN_IMAGE)" ]; then \
		echo "Set CONTAINER_SCAN_IMAGE to scan a built image with Trivy."; \
	elif command -v trivy >/dev/null 2>&1; then \
		trivy image \
			--severity "$(TRIVY_SEVERITY)" \
			--exit-code 1 \
			--ignore-unfixed \
			"$(CONTAINER_SCAN_IMAGE)"; \
	else \
		docker run --rm \
			-v /var/run/docker.sock:/var/run/docker.sock \
			-v "$$HOME/.cache/trivy:/root/.cache/trivy" \
			ghcr.io/aquasecurity/trivy:0.70.0@sha256:be1190afcb28352bfddc4ddeb71470835d16462af68d310f9f4bca710961a41e \
			image \
			--severity "$(TRIVY_SEVERITY)" \
			--exit-code 1 \
			--ignore-unfixed \
			"$(CONTAINER_SCAN_IMAGE)"; \
	fi

.PHONY: container-scan
container-scan: container-config-scan container-image-scan ## Scan container config and optional built image

.PHONY: security-readiness
security-readiness: ## Run local security checks before cloud mutation
	@$(MAKE) secret-scan
	@$(MAKE) dependency-audit

.PHONY: security-readiness-deep
security-readiness-deep: ## Run extended security scanners before sharing or release
	@$(MAKE) secret-scan
	@$(MAKE) secret-scan-deepfence
	@$(MAKE) dependency-audit
	@$(MAKE) dependency-audit-owasp
	@$(MAKE) container-scan
	@$(MAKE) lint-checkov
	@$(MAKE) lint-policy

.PHONY: lint-infra
lint-infra: ## Lint Terraform (fmt check + tflint + checkov)
	terraform fmt -check -recursive infra/
	@$(MAKE) lint-tflint
	@$(MAKE) lint-checkov

.PHONY: lint-tflint
lint-tflint: ## Run TFLint for Terraform roots
	cd infra/platform && tflint --init && tflint --format compact
	cd infra/app && tflint --init && tflint --format compact

.PHONY: lint-checkov
lint-checkov: ## Scan Terraform with Checkov
	checkov -d infra --framework terraform --config-file infra/.checkov.yaml

.PHONY: iac-scan
iac-scan: lint-checkov ## Alias for IaC scanning

.PHONY: policy-scan
policy-scan: lint-policy ## Alias for policy scanning

.PHONY: infra-validate-local
infra-validate-local: ## Validate Terraform syntax locally without backend or cloud mutation
	python3 scripts/ci/terraform_readiness.py

.PHONY: fmt
fmt: ## Auto-format Python and Terraform
	uv run ruff format apps/ examples/ packages/ tests/ scripts/
	terraform fmt -recursive infra/

.PHONY: pre-commit
pre-commit: ## Install and run prek-managed commit hooks
	uv run prek install -f
	uv run prek run --all-files --stage pre-commit

.PHONY: pre-push
pre-push: ## Install and run prek-managed push hooks
	uv run prek install -f
	uv run prek run --all-files --stage pre-push

# ── Cloud readiness proof ────────────────────────────────────────────────────

.PHONY: platform-toolkit-validate-cloud
platform-toolkit-validate-cloud: ## AWS ECS proof ladder: run safe cloud readiness checks
	@printf "\n==> Checking workload paved-road readiness\n"
	@$(MAKE) workload-readiness-check
	@printf "\n==> Running security readiness checks\n"
	@$(MAKE) security-readiness
	@printf "\n==> Linting GitHub workflow shape\n"
	@$(MAKE) lint-workflows
	@printf "\n==> Checking platform policy\n"
	@$(MAKE) lint-policy
	@printf "\n==> Validating Terraform syntax without backend mutation\n"
	@$(MAKE) infra-validate-local
	@printf "\n==> Validating generated workflow dry-run commands\n"
	@$(MAKE) workflow-dry-run-validate
	@printf "\n==> Running contract and operator-script tests\n"
	@uv run pytest tests/contracts tests/scripts -v

.PHONY: workflow-dry-run-commands
workflow-dry-run-commands: ## Print safe GitHub workflow dry-run dispatch commands
	@IMAGE_TAG="$(IMAGE_TAG)" PLAN_RUN_ID="$(PLAN_RUN_ID)" TARGET_WORKLOAD="$(TARGET_WORKLOAD)" SCHEMA_PHASE="$(SCHEMA_PHASE)" SWITCH_STEP="$(SWITCH_STEP)" \
		uv run python scripts/ci/workflow_dry_run_commands.py commands

.PHONY: workflow-dry-run-validate
workflow-dry-run-validate: ## Validate dry-run commands and non-mutating workflow guards
	uv run python scripts/ci/workflow_dry_run_commands.py validate-local

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

# ── Workload inventory & runtime evidence ────────────────────────────────────

.PHONY: monorepo-capability-profile
monorepo-capability-profile: ## Print derived delivery, workload, app-contract, and runtime capability profile
	@python3 -m scripts.platform.workload_metadata monorepo-capability-profile

.PHONY: monorepo-capability-profile-md
monorepo-capability-profile-md: ## Print the derived monorepo capability profile as compact Markdown
	@python3 -m scripts.platform.workload_metadata monorepo-capability-profile --format=markdown

.PHONY: monorepo-capability-profile-check
monorepo-capability-profile-check: ## Fail if expected delivery lanes or runtime capabilities disappear
	@python3 -m scripts.platform.workload_metadata monorepo-capability-profile --check

.PHONY: workload-capability-matrix
workload-capability-matrix: ## Print the declared workload capability matrix from platform/workloads.json
	python3 -m scripts.platform.workload_metadata capability-matrix

.PHONY: workload-readiness
workload-readiness: ## Static proof ladder: summarize runtime readiness and evidence surfaces
	@uv run python scripts/platform/workload_readiness.py --view summary

.PHONY: workload-readiness-local
workload-readiness-local: ## Static proof ladder: show local Compose and local Kubernetes readiness
	@uv run python scripts/platform/workload_readiness.py --view local

.PHONY: workload-readiness-cloud
workload-readiness-cloud: ## AWS ECS proof ladder: show cloud admission, workflow, and evidence readiness
	@uv run python scripts/platform/workload_readiness.py --view aws

.PHONY: workload-readiness-check
workload-readiness-check: ## Fail when declared workloads lack paved-road readiness
	@uv run python scripts/platform/workload_readiness.py --view summary --check

.PHONY: workload-fit-check
workload-fit-check: ## Evaluate a draft externally operated workload before admission
	@[ -n "$(WORKLOAD_CANDIDATE)" ] || (echo "Set WORKLOAD_CANDIDATE=/path/to/workload.json" >&2; exit 1)
	python3 scripts/platform/workload_fit_check.py --candidate "$(WORKLOAD_CANDIDATE)"

.PHONY: workload-admission-check
workload-admission-check: ## Validate repo-owned admission candidate samples
	@if [ -x .venv/bin/python ]; then \
		.venv/bin/python scripts/platform/admission_check.py; \
	else \
		uv run python scripts/platform/admission_check.py; \
	fi

.PHONY: capability-implementation-matrix
capability-implementation-matrix: ## Print the current runtime capability-to-implementation matrix
	python3 -m scripts.platform.workload_metadata implementation-matrix

.PHONY: local-compose-live-proof
local-compose-live-proof: ## Run isolated live local Compose proof
	python3 scripts/platform/local_compose_live_proof.py

.PHONY: runtime-defaults
runtime-defaults: ## Print blessed defaults for active runtime targets
	python3 -m scripts.platform.workload_metadata runtime-defaults

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
