#!/usr/bin/env bash
set -euo pipefail

TASK_FAMILY=${1:?"usage: ci_render_ecs_task_definition.sh <task-family> <container> <image> <output-json>"}
CONTAINER_NAME=${2:?"usage: ci_render_ecs_task_definition.sh <task-family> <container> <image> <output-json>"}
IMAGE=${3:?"usage: ci_render_ecs_task_definition.sh <task-family> <container> <image> <output-json>"}
OUTPUT_JSON=${4:?"usage: ci_render_ecs_task_definition.sh <task-family> <container> <image> <output-json>"}

aws ecs describe-task-definition \
  --task-definition "$TASK_FAMILY" \
  --query taskDefinition \
  --output json \
  | jq \
    --arg container "$CONTAINER_NAME" \
    --arg image "$IMAGE" \
    'del(
      .taskDefinitionArn,
      .revision,
      .status,
      .requiresAttributes,
      .compatibilities,
      .registeredAt,
      .registeredBy
    )
    | if .tags == [] then del(.tags) else . end
    | (.containerDefinitions[] | select(.name == $container) | .image) = $image' \
    > "$OUTPUT_JSON"

if ! jq -e --arg container "$CONTAINER_NAME" '
  [.containerDefinitions[].name] | index($container) != null
' "$OUTPUT_JSON" > /dev/null; then
  echo "container ${CONTAINER_NAME} not found in task family ${TASK_FAMILY}" >&2
  exit 1
fi
