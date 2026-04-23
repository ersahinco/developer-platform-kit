#!/usr/bin/env bash
# db_seed_tunnel.sh — open an SSM tunnel to RDS and run seed_data.py
# Usage: db_seed_tunnel.sh <num_customers> <num_orders> <aws_region>
set -euo pipefail

SEED_NUM_CUSTOMERS=${1:-1000}
SEED_NUM_ORDERS=${2:-10000}
AWS_REGION=${3:-eu-central-1}

cd "$(dirname "$0")/.."

echo "→ resolving infra outputs for single stack"
cd infra
terraform init \
  -backend-config="key=aws-sdlc-containers/stack.tfstate" \
  -reconfigure -input=false > /dev/null 2>&1

CLUSTER=$(terraform output -raw ecs_cluster_name)
SERVICE=$(terraform output -raw app_service_name)
RDS_HOST=$(terraform output -raw rds_endpoint | cut -d: -f1)
SECRET_ARN=$(terraform output -raw db_secret_arn)
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

TASK_ID=$(echo "$TASK_ARN" | awk -F/ '{print $NF}')

RUNTIME_ID=$(aws ecs describe-tasks \
  --cluster "$CLUSTER" \
  --tasks "$TASK_ARN" \
  --region "$AWS_REGION" \
  --query 'tasks[0].containers[?name==`app`].runtimeId' \
  --output text)

[ -n "$RUNTIME_ID" ] \
  || { echo "ERROR: could not resolve runtimeId for app container in task $TASK_ID"; exit 1; }

SECRET=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ARN" \
  --query SecretString --output text)
DB_USER=$(echo "$SECRET" | python3 -c "import sys,json; print(json.load(sys.stdin)['username'])")
DB_PASS=$(echo "$SECRET" | python3 -c "import sys,json; print(json.load(sys.stdin)['password'])")

echo "→ opening SSM tunnel localhost:15433 → $RDS_HOST:5432 via task $TASK_ID"
aws ssm start-session \
  --target "ecs:${CLUSTER}_${TASK_ID}_${RUNTIME_ID}" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "{\"host\":[\"$RDS_HOST\"],\"portNumber\":[\"5432\"],\"localPortNumber\":[\"15433\"]}" \
  --region "$AWS_REGION" &
SSM_PID=$!

echo "→ waiting for tunnel on port 15433…"
for i in $(seq 1 20); do
  nc -z localhost 15433 2>/dev/null && break
  sleep 1
done
nc -z localhost 15433 2>/dev/null \
  || { echo "ERROR: tunnel did not open"; kill $SSM_PID 2>/dev/null; exit 1; }

echo "→ seeding DB (SEED_NUM_CUSTOMERS=$SEED_NUM_CUSTOMERS, SEED_NUM_ORDERS=$SEED_NUM_ORDERS)"
DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@localhost:15433/aws_sdlc_containers" \
  SEED_NUM_CUSTOMERS="$SEED_NUM_CUSTOMERS" \
  SEED_NUM_ORDERS="$SEED_NUM_ORDERS" \
  uv run python scripts/seed_data.py
SEED_EXIT=$?

kill $SSM_PID 2>/dev/null || true
exit $SEED_EXIT
