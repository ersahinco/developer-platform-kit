#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${1:?"usage: ci_deploy_ecs_service.sh <cluster> <service> <task-definition-json>"}
SERVICE=${2:?"usage: ci_deploy_ecs_service.sh <cluster> <service> <task-definition-json>"}
TASK_DEFINITION_PATH=${3:?"usage: ci_deploy_ecs_service.sh <cluster> <service> <task-definition-json>"}

TASK_DEF_ARN=$(aws ecs register-task-definition \
  --cli-input-json "file://${TASK_DEFINITION_PATH}" \
  --query 'taskDefinition.taskDefinitionArn' \
  --output text)

if [[ -z "$TASK_DEF_ARN" || "$TASK_DEF_ARN" == "None" ]]; then
  echo "Failed to register task definition from ${TASK_DEFINITION_PATH}" >&2
  exit 1
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "task_def_arn=${TASK_DEF_ARN}" >> "$GITHUB_OUTPUT"
fi

aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "$SERVICE" \
  --task-definition "$TASK_DEF_ARN" \
  > /dev/null

if [[ "${ECS_DEPLOY_WAIT_FOR_STABLE:-true}" == "true" ]]; then
  aws ecs wait services-stable \
    --cluster "$CLUSTER" \
    --services "$SERVICE"
fi

echo "Service ${SERVICE} updated to ${TASK_DEF_ARN}"
