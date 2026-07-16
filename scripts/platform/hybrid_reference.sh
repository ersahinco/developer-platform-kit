#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
RUNTIME_SOURCE="$ROOT/infra/hybrid-reference/compute/runtime"
DAPR_SOURCE="$ROOT/platform/concerns/dapr/profiles/local"
REMOTE_USER=${HYBRID_SSH_USER:-platform}
REMOTE_HOST=${HYBRID_SSH_HOST:-}
REMOTE_DIR=${HYBRID_RUNTIME_DIR:-/opt/aws-sdlc-containers}
SSH_OPTIONS=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new)

fail() {
  printf '%s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

require_env() {
  [[ -n ${!1:-} ]] || fail "Required environment variable is not set: $1"
}

require_digest_ref() {
  local name=$1
  local value=${!name:-}
  [[ $value =~ ^[^[:space:]]+@sha256:[0-9a-f]{64}$ ]] ||
    fail "$name must be an OCI reference pinned with @sha256:<64 lowercase hex characters>"
}

require_remote() {
  require_command ssh
  require_env HYBRID_SSH_HOST
  [[ $REMOTE_USER =~ ^[a-z_][a-z0-9_-]*$ ]] || fail "HYBRID_SSH_USER is invalid"
  [[ $REMOTE_HOST =~ ^[a-zA-Z0-9._:-]+$ ]] || fail "HYBRID_SSH_HOST is invalid"
  [[ $REMOTE_DIR =~ ^/[a-zA-Z0-9._/-]+$ ]] || fail "HYBRID_RUNTIME_DIR is invalid"
}

remote() {
  # Callers compose commands from validated identifiers for the remote shell.
  # shellcheck disable=SC2029
  ssh "${SSH_OPTIONS[@]}" "${REMOTE_USER}@${REMOTE_HOST}" "$@"
}

dotenv_value() {
  local value=$1
  [[ $value != *$'\n'* && $value != *$'\r'* ]] || fail "Runtime values must be single-line"
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//\$/\\\$}
  printf '"%s"' "$value"
}

write_runtime_env() {
  local names=(
    HYBRID_HOSTNAME ACME_EMAIL POOLED_DATABASE_URL DIRECT_DATABASE_URL PRIMARY_EDGE_AUTH_TOKEN
    LIQUIBASE_DATABASE_URL LIQUIBASE_DATABASE_USERNAME LIQUIBASE_DATABASE_PASSWORD
    DATA_EXPORT_BUCKET AWS_REGION API_IMAGE BOOKING_API_IMAGE EVENT_CONSUMER_IMAGE
    DATA_EXPORT_IMAGE LIQUIBASE_IMAGE
  )
  {
    local name
    for name in "${names[@]}"; do
      printf '%s=' "$name"
      dotenv_value "${!name:-}"
      printf '\n'
    done
    printf 'AWS_ACCESS_KEY_ID='
    dotenv_value "$DATA_EXPORT_AWS_ACCESS_KEY_ID"
    printf '\nAWS_SECRET_ACCESS_KEY='
    dotenv_value "$DATA_EXPORT_AWS_SECRET_ACCESS_KEY"
    printf '\nAWS_SESSION_TOKEN='
    dotenv_value "${DATA_EXPORT_AWS_SESSION_TOKEN:-}"
    printf '\n'
  } | remote "umask 077; cat > '$REMOTE_DIR/.env' && chmod 0600 '$REMOTE_DIR/.env'"
}

check_prerequisites() {
  for command in aws curl dig jq scp ssh; do
    require_command "$command"
  done
  aws sts get-caller-identity >/dev/null
  printf '%s\n' "Hybrid reference client prerequisites are available."
}

deploy() {
  require_remote
  for name in HYBRID_HOSTNAME ACME_EMAIL POOLED_DATABASE_URL DIRECT_DATABASE_URL PRIMARY_EDGE_AUTH_TOKEN \
    LIQUIBASE_DATABASE_URL LIQUIBASE_DATABASE_USERNAME \
    LIQUIBASE_DATABASE_PASSWORD DATA_EXPORT_BUCKET AWS_REGION \
    DATA_EXPORT_AWS_ACCESS_KEY_ID DATA_EXPORT_AWS_SECRET_ACCESS_KEY; do
    require_env "$name"
  done
  [[ $HYBRID_HOSTNAME =~ ^[a-z0-9.-]+$ ]] || fail "HYBRID_HOSTNAME is invalid"
  for name in API_IMAGE BOOKING_API_IMAGE EVENT_CONSUMER_IMAGE DATA_EXPORT_IMAGE LIQUIBASE_IMAGE; do
    require_digest_ref "$name"
  done

  remote "cloud-init status --wait >/dev/null; install -d -m 0750 '$REMOTE_DIR/dapr/components'"
  scp "${SSH_OPTIONS[@]}" \
    "$RUNTIME_SOURCE/compose.yaml" \
    "$RUNTIME_SOURCE/Caddyfile" \
    "${REMOTE_USER}@${REMOTE_HOST}:$REMOTE_DIR/"
  scp "${SSH_OPTIONS[@]}" \
    "$DAPR_SOURCE/config.yaml" \
    "${REMOTE_USER}@${REMOTE_HOST}:$REMOTE_DIR/dapr/config.yaml"
  scp "${SSH_OPTIONS[@]}" "$DAPR_SOURCE/components/"*.yaml \
    "${REMOTE_USER}@${REMOTE_HOST}:$REMOTE_DIR/dapr/components/"
  write_runtime_env

  if [[ -n ${REGISTRY_PASSWORD:-} || -n ${REGISTRY_USERNAME:-} || -n ${REGISTRY_HOST:-} ]]; then
    require_env REGISTRY_PASSWORD
    require_env REGISTRY_USERNAME
    require_env REGISTRY_HOST
    [[ $REGISTRY_HOST =~ ^[a-zA-Z0-9._:-]+$ ]] || fail "REGISTRY_HOST contains unsupported characters"
    [[ $REGISTRY_USERNAME =~ ^[a-zA-Z0-9._@:-]+$ ]] || fail "REGISTRY_USERNAME contains unsupported characters"
    printf '%s' "$REGISTRY_PASSWORD" |
      remote "set -e
docker_config=\$(mktemp -d)
trap 'rm -rf \"\$docker_config\"' EXIT
export DOCKER_CONFIG=\"\$docker_config\"
docker login '$REGISTRY_HOST' --username '$REGISTRY_USERNAME' --password-stdin
cd '$REMOTE_DIR'
docker compose --env-file .env config --quiet
docker compose --env-file .env pull
docker compose --env-file .env up -d --remove-orphans"
  else
    remote "cd '$REMOTE_DIR' && docker compose --env-file .env config --quiet && docker compose --env-file .env pull && docker compose --env-file .env up -d --remove-orphans"
  fi
  printf '%s\n' "Digest-pinned hybrid runtime deployed to $REMOTE_HOST."
}

migrate() {
  require_remote
  remote "cd '$REMOTE_DIR' && docker compose --env-file .env --profile migration run --rm liquibase update"
}

verify_origin() {
  require_remote
  remote "REMOTE_DIR='$REMOTE_DIR' bash -s" <<'REMOTE'
set -euo pipefail
cd "$REMOTE_DIR"
compose=(docker compose --env-file .env)

for attempt in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:8080/ready >/dev/null; then
    break
  fi
  [[ $attempt -lt 30 ]] || { echo "Origin readiness timed out" >&2; exit 1; }
  sleep 2
done

curl --fail --silent http://127.0.0.1:8080/health >/dev/null
curl --fail --silent http://127.0.0.1:8080/ready >/dev/null
metrics=$(curl --fail --silent http://127.0.0.1:8080/metrics)
grep -q 'workload_info{workload="api"' <<<"$metrics"
curl --fail --silent http://127.0.0.1:8080/ready >/dev/null
"${compose[@]}" logs --no-color --tail 200 api | grep -q '"workload": "api"'

for attempt in $(seq 1 30); do
  metadata=$(curl --fail --silent http://127.0.0.1:3500/v1.0/metadata || true)
  if jq -e '.components[] | select(.name == "async-events-pubsub" and (.type | startswith("pubsub.")))' <<<"$metadata" >/dev/null 2>&1; then
    break
  fi
  [[ $attempt -lt 30 ]] || { echo "Dapr component readiness timed out" >&2; exit 1; }
  sleep 2
done

curl --fail --silent http://127.0.0.1:3500/v1.0/invoke/booking-api/method/ready |
  jq -e '.status == "ready"' >/dev/null

event_id="order.created.v1:hybrid-smoke-$(date -u +%Y%m%dT%H%M%SZ)-$RANDOM"
occurred_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
event=$(jq -cn \
  --arg id "$event_id" \
  --arg occurred_at "$occurred_at" \
  '{specversion:"1.0",id:$id,source:"aws-sdlc-containers/events",type:"order.created.v1",datacontenttype:"application/json",data:{event_type:"order.created.v1",event_version:1,event_id:$id,idempotency_key:$id,aggregate_type:"order",aggregate_id:260528,occurred_at:$occurred_at,order:{id:260528,customer_id:1,total_amount:"10.00",status:"SUBMITTED",submitted_at:$occurred_at,created_at:$occurred_at}}}')
for _ in 1 2; do
  curl --fail --silent \
    -H 'Content-Type: application/cloudevents+json' \
    --data "$event" \
    "http://127.0.0.1:3500/v1.0/publish/async-events-pubsub/async-events-v1.fifo" >/dev/null
done

"${compose[@]}" --profile operations run --rm --no-deps -e EVENT_ID="$event_id" data-export \
  python -c 'import os,time; from sqlalchemy import create_engine,text; engine=create_engine(os.environ["DATABASE_URL"]); deadline=time.time()+30; row=None
while time.time()<deadline:
  with engine.connect() as connection: row=connection.execute(text("select status, duplicate_count from event_receipts where event_id=:event_id"), {"event_id":os.environ["EVENT_ID"]}).mappings().first()
  if row and row["duplicate_count"] >= 1: break
  time.sleep(1)
assert row and row["status"] in {"processed","duplicate","ignored_stale"} and row["duplicate_count"] >= 1, row
print(dict(row))'

printf '%s\n' '{"event":"hybrid_origin_verification_succeeded","runtime_id":"hetzner-compose","dapr_invocation":true,"dapr_pubsub":true,"duplicate_event":true}'
REMOTE
}

verify_public() {
  require_env HYBRID_HOSTNAME
  [[ $HYBRID_HOSTNAME =~ ^[a-z0-9.-]+$ ]] || fail "HYBRID_HOSTNAME is invalid"
  require_command dig
  resolved_ipv4=$(dig +short A "$HYBRID_HOSTNAME")
  [[ -n $resolved_ipv4 ]] || fail "No A record resolved for $HYBRID_HOSTNAME"
  if [[ -n ${HYBRID_ORIGIN_IPV4:-} ]]; then
    grep -Fxq "$HYBRID_ORIGIN_IPV4" <<<"$resolved_ipv4" ||
      fail "$HYBRID_HOSTNAME does not resolve to $HYBRID_ORIGIN_IPV4"
  fi
  for path in health ready metrics; do
    curl --fail --show-error --silent --retry 12 --retry-delay 5 \
      "https://$HYBRID_HOSTNAME/$path" >/dev/null
  done
  printf '%s\n' "Public DNS, TLS, health, readiness, and metrics verification passed."
}

run_export() {
  require_remote
  output=$(remote "cd '$REMOTE_DIR' && docker compose --env-file .env --profile operations run --rm data-export")
  printf '%s\n' "$output"
  jq -e 'select(.event == "data_export_succeeded" and .status == "succeeded" and .raw_sha256 and .objects.manifest)' <<<"$output" >/dev/null
}

drill_database_unavailable() {
  require_remote
  if remote "cd '$REMOTE_DIR' && docker compose --env-file .env --profile operations run --rm --no-deps -e DATABASE_URL=postgresql://invalid.invalid:5432/unavailable data-export python -c 'from sqlalchemy import create_engine; create_engine(\"postgresql://invalid.invalid:5432/unavailable\").connect()'"; then
    fail "Database-unavailability drill unexpectedly connected"
  fi
  printf '%s\n' "Database-unavailability failure was detected as expected."
}

drill_invalid_s3() {
  require_remote
  if remote "cd '$REMOTE_DIR' && docker compose --env-file .env --profile operations run --rm -e AWS_ACCESS_KEY_ID=invalid -e AWS_SECRET_ACCESS_KEY=invalid data-export"; then
    fail "Invalid-S3-credentials drill unexpectedly succeeded"
  fi
  printf '%s\n' "Invalid S3 credentials produced a failed export as expected."
}

action=${1:-}
case "$action" in
  prerequisites) check_prerequisites ;;
  deploy) deploy ;;
  migrate) migrate ;;
  verify-origin) verify_origin ;;
  verify-public) verify_public ;;
  export) run_export ;;
  drill-database-unavailable) drill_database_unavailable ;;
  drill-invalid-s3) drill_invalid_s3 ;;
  *) fail "Usage: $0 {prerequisites|deploy|migrate|verify-origin|verify-public|export|drill-database-unavailable|drill-invalid-s3}" ;;
esac
