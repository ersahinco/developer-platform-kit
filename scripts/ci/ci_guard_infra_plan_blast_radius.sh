#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 <terraform-plan-output-file>" >&2
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

plan_output="$1"
allow_ecs_task_definition_changes="${ALLOW_ECS_TASK_DEFINITION_CHANGES:-}"
ecs_task_definition_pattern='^[[:space:]]*# .*aws_ecs_task_definition.*(will be|must be)'

if [[ ! -f "$plan_output" ]]; then
  echo "Terraform plan output file not found: $plan_output" >&2
  exit 2
fi

matches="$(grep -En "$ecs_task_definition_pattern" "$plan_output" || true)"
matches="$(printf "%s\n" "$matches" | grep -Ev '^[0-9]+:[[:space:]]*# data\.' || true)"

if [[ -n "$matches" ]]; then
  if [[ "$allow_ecs_task_definition_changes" != "allow-ecs-task-definition-changes" ]]; then
    echo "Reviewed app plan contains ECS task definition changes." >&2
    echo "This can roll infra apply across the app deploy ownership boundary." >&2
    echo "Re-run only after reviewing the plan and setting allow_ecs_task_definition_changes=allow-ecs-task-definition-changes." >&2
    printf "%s\n" "$matches" >&2
    exit 1
  fi
fi
