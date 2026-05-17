#!/usr/bin/env bash
set -euo pipefail

TASK_DEFINITION_PATH=${1:?"usage: ci_register_ecs_task_definition.sh <task-definition-json>"}
OUTPUT_FILE=${GITHUB_OUTPUT:-}

python3 scripts/ci/ci_strip_empty_tags.py "$TASK_DEFINITION_PATH"

TASK_DEF_ARN=$(aws ecs register-task-definition \
  --cli-input-json "file://${TASK_DEFINITION_PATH}" \
  --query 'taskDefinition.taskDefinitionArn' \
  --output text)

if [ -z "$TASK_DEF_ARN" ] || [ "$TASK_DEF_ARN" = "None" ]; then
  echo "Failed to register task definition from ${TASK_DEFINITION_PATH}" >&2
  exit 1
fi

echo "Registered task definition: ${TASK_DEF_ARN}" >&2

if [ -n "$OUTPUT_FILE" ]; then
  echo "task_def_arn=${TASK_DEF_ARN}" >> "$OUTPUT_FILE"
fi

printf '%s\n' "$TASK_DEF_ARN"
