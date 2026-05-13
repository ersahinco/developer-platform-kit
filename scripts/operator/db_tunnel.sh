#!/usr/bin/env bash
# db_tunnel.sh — SSM port-forward localhost:LOCAL_PORT → RDS:5432
# Usage: db_tunnel.sh <local_port> <aws_region>
set -euo pipefail

LOCAL_PORT=${1:-15432}
AWS_REGION=${2:-${AWS_REGION:-eu-central-1}}

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
SERVICE=$(terraform output -raw app_service_name)
RDS_HOST=$(terraform output -raw rds_endpoint | cut -d: -f1)
SECRET_ARN=$(terraform output -raw db_secret_arn)
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

TASK_ID=$(echo "$TASK_ARN" | awk -F/ '{print $NF}')

RUNTIME_ID=$(aws ecs describe-tasks \
  --cluster "$CLUSTER" \
  --tasks "$TASK_ARN" \
  --region "$AWS_REGION" \
  --query 'tasks[0].containers[?name==`app`].runtimeId' \
  --output text)

[ -n "$RUNTIME_ID" ] \
  || { echo "ERROR: could not resolve runtimeId for app container in task $TASK_ID"; exit 1; }

echo "→ tunnel localhost:$LOCAL_PORT → $RDS_HOST:5432 via task $TASK_ID"
echo "  Connect DBeaver/psql to: host=localhost  port=$LOCAL_PORT  dbname=aws_sdlc_containers"
echo "  Get credentials: aws secretsmanager get-secret-value --secret-id $SECRET_ARN --query SecretString --output text | python3 -m json.tool"

aws ssm start-session \
  --target "ecs:${CLUSTER}_${TASK_ID}_${RUNTIME_ID}" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "{\"host\":[\"$RDS_HOST\"],\"portNumber\":[\"5432\"],\"localPortNumber\":[\"$LOCAL_PORT\"]}" \
  --region "$AWS_REGION"
