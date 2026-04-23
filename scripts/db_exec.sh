#!/usr/bin/env bash
# db_exec.sh — open psql inside a running app ECS task via ECS Exec
# Usage: db_exec.sh <env> <aws_region>
set -euo pipefail

ENV=${1:-dev}
AWS_REGION=${2:-eu-central-1}

cd "$(dirname "$0")/.."

cd infra
terraform init \
  -backend-config="key=aws-sdlc-containers/${ENV}.tfstate" \
  -reconfigure -input=false > /dev/null 2>&1

CLUSTER=$(terraform output -raw ecs_cluster_name)
SERVICE=$(terraform output -raw app_service_name)
cd ..

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
  --container app \
  --interactive \
  --command 'psql $DATABASE_URL' \
  --region "$AWS_REGION"
