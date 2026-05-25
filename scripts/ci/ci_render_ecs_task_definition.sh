#!/usr/bin/env bash
set -euo pipefail

TASK_FAMILY=${1:?"usage: ci_render_ecs_task_definition.sh <task-family> <container> <image> <output-json>"}
CONTAINER_NAME=${2:?"usage: ci_render_ecs_task_definition.sh <task-family> <container> <image> <output-json>"}
IMAGE=${3:?"usage: ci_render_ecs_task_definition.sh <task-family> <container> <image> <output-json>"}
OUTPUT_JSON=${4:?"usage: ci_render_ecs_task_definition.sh <task-family> <container> <image> <output-json>"}

python3 scripts/ci/render_ecs_task_definition.py \
  "$TASK_FAMILY" \
  "$CONTAINER_NAME" \
  "$IMAGE" \
  "$OUTPUT_JSON"
