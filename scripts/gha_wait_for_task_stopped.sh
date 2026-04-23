#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${1:?"usage: gha_wait_for_task_stopped.sh <cluster> <task-arn>"}
TASK_ARN=${2:?"usage: gha_wait_for_task_stopped.sh <cluster> <task-arn>"}

aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN"
