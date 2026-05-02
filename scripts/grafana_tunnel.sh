#!/usr/bin/env bash
# grafana_tunnel.sh — SSM port-forward localhost:LOCAL_PORT → private Grafana:3000
# Usage: grafana_tunnel.sh <local_port> <aws_region>
set -euo pipefail

LOCAL_PORT=${1:-3000}
AWS_REGION=${2:-eu-central-1}

cd "$(dirname "$0")/.."

cd infra/app
terraform init \
  -backend-config="key=aws-sdlc-containers/app.tfstate" \
  -reconfigure -input=false > /dev/null 2>&1

CLUSTER=$(terraform output -raw ecs_cluster_name)
SERVICE=$(terraform output -raw observability_grafana_service_name)
cd ../..

[ -n "$SERVICE" ] && [ "$SERVICE" != "null" ] \
  || { echo "ERROR: observability Grafana service is not enabled"; exit 1; }

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
  --query 'tasks[0].containers[?name==`grafana`].runtimeId' \
  --output text)

[ -n "$RUNTIME_ID" ] \
  || { echo "ERROR: could not resolve runtimeId for grafana container in task $TASK_ID"; exit 1; }

echo "-> tunnel http://localhost:$LOCAL_PORT -> grafana.${CLUSTER}.local:3000 via task $TASK_ID"
echo "   Open Grafana at: http://localhost:$LOCAL_PORT"

aws ssm start-session \
  --target "ecs:${CLUSTER}_${TASK_ID}_${RUNTIME_ID}" \
  --document-name AWS-StartPortForwardingSession \
  --parameters "{\"portNumber\":[\"3000\"],\"localPortNumber\":[\"$LOCAL_PORT\"]}" \
  --region "$AWS_REGION"
