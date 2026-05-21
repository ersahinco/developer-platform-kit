#!/usr/bin/env bash
# db_exec.sh — open psql inside the running primary edge ECS task via ECS Exec
# Usage: db_exec.sh <aws_region>
set -euo pipefail

AWS_REGION=${1:-${AWS_REGION:-eu-central-1}}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$ROOT_DIR"

STACK_NAME=${STACK_NAME:-$(basename "$ROOT_DIR")}
TF_APP_STATE_KEY=${TF_APP_STATE_KEY:-${STACK_NAME}/app.tfstate}
if [ -z "${TF_STATE_BUCKET:-}" ]; then
  ACCOUNT_ID=${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION" 2>/dev/null)}
  [ -n "$ACCOUNT_ID" ] || { echo "ERROR: set TF_STATE_BUCKET or configure AWS credentials."; exit 1; }
  TF_STATE_BUCKET="${STACK_NAME}-tfstate-${ACCOUNT_ID}"
fi

cd infra/app
terraform init \
  -backend-config="bucket=${TF_STATE_BUCKET}" \
  -backend-config="key=${TF_APP_STATE_KEY}" \
  -backend-config="region=${AWS_REGION}" \
  -reconfigure -input=false > /dev/null 2>&1

CLUSTER=$(terraform output -raw ecs_cluster_name)
SERVICE=$(terraform output -raw primary_edge_service_name)
cd ../..

TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER" \
  --service-name "$SERVICE" \
  --desired-status RUNNING \
  --query 'taskArns[0]' \
  --output text \
  --region "$AWS_REGION")

[ -n "$TASK_ARN" ] && [ "$TASK_ARN" != "None" ] \
  || { echo "ERROR: no running task in $CLUSTER/$SERVICE"; exit 1; }

echo "→ exec into task $TASK_ARN"
aws ecs execute-command \
  --cluster "$CLUSTER" \
  --task "$TASK_ARN" \
  --container "$SERVICE" \
  --interactive \
  --command 'psql $DATABASE_URL' \
  --region "$AWS_REGION"
