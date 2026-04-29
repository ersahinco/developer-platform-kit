#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${1:?"usage: ci_run_ecs_task.sh <cluster> <task-definition> <subnet-id> <security-group-id>"}
TASK_DEFINITION=${2:?"usage: ci_run_ecs_task.sh <cluster> <task-definition> <subnet-id> <security-group-id>"}
SUBNET_ID=${3:?"usage: ci_run_ecs_task.sh <cluster> <task-definition> <subnet-id> <security-group-id>"}
SG_ID=${4:?"usage: ci_run_ecs_task.sh <cluster> <task-definition> <subnet-id> <security-group-id>"}
LAUNCH_TYPE=${ECS_RUN_TASK_LAUNCH_TYPE:-FARGATE}
ASSIGN_PUBLIC_IP=${ECS_RUN_TASK_ASSIGN_PUBLIC_IP:-DISABLED}

TASK_ARN=$(aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASK_DEFINITION" \
  --launch-type "$LAUNCH_TYPE" \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_ID}],securityGroups=[${SG_ID}],assignPublicIp=${ASSIGN_PUBLIC_IP}}" \
  --query 'tasks[0].taskArn' \
  --output text)

if [ -z "$TASK_ARN" ] || [ "$TASK_ARN" = "None" ]; then
  echo "Failed to start ECS task ${TASK_DEFINITION} on cluster ${CLUSTER}" >&2
  exit 1
fi

echo "Started task: ${TASK_ARN}" >&2
printf '%s\n' "$TASK_ARN"
