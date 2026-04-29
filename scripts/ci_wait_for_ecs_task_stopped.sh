#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${1:?"usage: ci_wait_for_ecs_task_stopped.sh <cluster> <task-arn>"}
TASK_ARN=${2:?"usage: ci_wait_for_ecs_task_stopped.sh <cluster> <task-arn>"}

aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN"
