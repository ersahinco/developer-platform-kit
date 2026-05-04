#!/usr/bin/env bash
set -euo pipefail

TASK_DEFINITION_PATH=${1:?"usage: ci_register_ecs_task_definition.sh <task-definition-json>"}
OUTPUT_FILE=${GITHUB_OUTPUT:-}

python3 - "$TASK_DEFINITION_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
task_definition = json.loads(path.read_text(encoding="utf-8"))

if task_definition.get("tags") == []:
    del task_definition["tags"]

path.write_text(json.dumps(task_definition, indent=2) + "\n", encoding="utf-8")
PY

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
