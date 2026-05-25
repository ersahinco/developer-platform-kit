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

service_matches="$(
  awk '
    BEGIN {in_service = 0; block = ""; found = 0}
    /^[[:space:]]*# .*aws_ecs_service\.(primary_edge|event_consumer) / {
      in_service = 1
      block = $0 "\n"
      next
    }
    in_service {
      block = block $0 "\n"
      if ($0 ~ /^[[:space:]]*}/) {
        if (block ~ /desired_count[[:space:]]*=[[:space:]]*[0-9]+[[:space:]]*->[[:space:]]*[0-9]+/) {
          printf "%s", block
          found = 1
        }
        in_service = 0
        block = ""
      }
    }
    END {
      if (in_service && block ~ /desired_count[[:space:]]*=[[:space:]]*[0-9]+[[:space:]]*->[[:space:]]*[0-9]+/) {
        printf "%s", block
        found = 1
      }
      exit found ? 0 : 1
    }
  ' "$plan_output" || true
)"

if [[ -n "$service_matches" ]]; then
  echo "Reviewed app plan changes ECS service desired_count." >&2
  echo "Desired rollout settings belong to app deploy, not infra apply." >&2
  echo "Fix the ownership seam before applying this plan." >&2
  printf "%s\n" "$service_matches" >&2
  exit 1
fi
