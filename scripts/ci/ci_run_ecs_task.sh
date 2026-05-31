#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${1:?"usage: ci_run_ecs_task.sh <cluster> <task-definition> <subnet-id> <security-group-id>"}
TASK_DEFINITION=${2:?"usage: ci_run_ecs_task.sh <cluster> <task-definition> <subnet-id> <security-group-id>"}
SUBNET_ID=${3:?"usage: ci_run_ecs_task.sh <cluster> <task-definition> <subnet-id> <security-group-id>"}
SG_ID=${4:?"usage: ci_run_ecs_task.sh <cluster> <task-definition> <subnet-id> <security-group-id>"}
LAUNCH_TYPE=${ECS_RUN_TASK_LAUNCH_TYPE:-FARGATE}
ASSIGN_PUBLIC_IP=${ECS_RUN_TASK_ASSIGN_PUBLIC_IP:-DISABLED}
WAIT_FOR_STOPPED=${ECS_RUN_TASK_WAIT_FOR_STOPPED:-false}
ASSERT_SUCCESS=${ECS_RUN_TASK_ASSERT_SUCCESS:-false}
LABEL=${ECS_RUN_TASK_LABEL:-Task}
OVERRIDES_JSON=${ECS_RUN_TASK_OVERRIDES_JSON:-}
STARTED_BY=${ECS_RUN_TASK_STARTED_BY:-}

run_task_args=(
  aws ecs run-task
  --cluster "$CLUSTER"
  --task-definition "$TASK_DEFINITION"
  --launch-type "$LAUNCH_TYPE"
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_ID}],securityGroups=[${SG_ID}],assignPublicIp=${ASSIGN_PUBLIC_IP}}"
  --query 'tasks[0].taskArn'
  --output text
)

if [[ -n "$OVERRIDES_JSON" ]]; then
  run_task_args+=(--overrides "$OVERRIDES_JSON")
fi

if [[ -n "$STARTED_BY" ]]; then
  run_task_args+=(--started-by "$STARTED_BY")
fi

TASK_ARN=$("${run_task_args[@]}")

if [ -z "$TASK_ARN" ] || [ "$TASK_ARN" = "None" ]; then
  echo "Failed to start ECS task ${TASK_DEFINITION} on cluster ${CLUSTER}" >&2
  exit 1
fi

echo "Started task: ${TASK_ARN}" >&2

if [[ "$WAIT_FOR_STOPPED" == "true" ]]; then
  aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN"
fi

if [[ "$ASSERT_SUCCESS" == "true" ]]; then
  EXIT_CODE=$(aws ecs describe-tasks \
    --cluster "$CLUSTER" \
    --tasks "$TASK_ARN" \
    --query 'tasks[0].containers[0].exitCode' \
    --output text)

  if [[ "$EXIT_CODE" == "None" || "$EXIT_CODE" != "0" ]]; then
    REASON=$(aws ecs describe-tasks \
      --cluster "$CLUSTER" \
      --tasks "$TASK_ARN" \
      --query 'tasks[0].stoppedReason' \
      --output text)
    echo "${LABEL} failed (exit ${EXIT_CODE}) - stoppedReason: ${REASON}" >&2
    exit 1
  fi
fi

printf '%s\n' "$TASK_ARN"
