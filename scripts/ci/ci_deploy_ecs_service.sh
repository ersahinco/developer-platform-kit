#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CLUSTER=${1:?"usage: ci_deploy_ecs_service.sh <cluster> <service> <task-definition-json>"}
SERVICE=${2:?"usage: ci_deploy_ecs_service.sh <cluster> <service> <task-definition-json>"}
TASK_DEFINITION_PATH=${3:?"usage: ci_deploy_ecs_service.sh <cluster> <service> <task-definition-json>"}

TASK_DEF_ARN=$(GITHUB_OUTPUT= "${SCRIPT_DIR}/ci_register_ecs_task_definition.sh" "$TASK_DEFINITION_PATH")

aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "$SERVICE" \
  --task-definition "$TASK_DEF_ARN" \
  > /dev/null

aws ecs wait services-stable \
  --cluster "$CLUSTER" \
  --services "$SERVICE"

echo "Service ${SERVICE} updated to ${TASK_DEF_ARN}"
