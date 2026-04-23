#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${1:?"usage: gha_assert_task_succeeded.sh <cluster> <task-arn> [label]"}
TASK_ARN=${2:?"usage: gha_assert_task_succeeded.sh <cluster> <task-arn> [label]"}
LABEL=${3:-Task}

EXIT_CODE=$(aws ecs describe-tasks \
  --cluster "$CLUSTER" \
  --tasks "$TASK_ARN" \
  --query 'tasks[0].containers[0].exitCode' \
  --output text)

if [ "$EXIT_CODE" = "None" ] || [ "$EXIT_CODE" != "0" ]; then
  REASON=$(aws ecs describe-tasks \
    --cluster "$CLUSTER" \
    --tasks "$TASK_ARN" \
    --query 'tasks[0].stoppedReason' \
    --output text)
  echo "${LABEL} failed (exit ${EXIT_CODE}) - stoppedReason: ${REASON}" >&2
  exit 1
fi
