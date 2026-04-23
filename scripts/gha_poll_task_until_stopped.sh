#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${1:?"usage: gha_poll_task_until_stopped.sh <cluster> <task-arn> [label]"}
TASK_ARN=${2:?"usage: gha_poll_task_until_stopped.sh <cluster> <task-arn> [label]"}
LABEL=${3:-Task}
SLEEP_SECONDS=${ECS_TASK_POLL_SECONDS:-10}

while true; do
  STATUS=$(aws ecs describe-tasks \
    --cluster "$CLUSTER" \
    --tasks "$TASK_ARN" \
    --query 'tasks[0].lastStatus' \
    --output text)

  if [ "$STATUS" = "STOPPED" ]; then
    break
  fi

  echo "${LABEL} status: ${STATUS} - waiting..."
  sleep "$SLEEP_SECONDS"
done
