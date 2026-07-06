#!/usr/bin/env bash
set -euo pipefail

CLUSTER=${1:?"usage: ci_deploy_ecs_service.sh <cluster> <service> <task-definition-json> [desired-count]"}
SERVICE=${2:?"usage: ci_deploy_ecs_service.sh <cluster> <service> <task-definition-json> [desired-count]"}
TASK_DEFINITION_PATH=${3:?"usage: ci_deploy_ecs_service.sh <cluster> <service> <task-definition-json> [desired-count]"}
DESIRED_COUNT=${4:-}

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

echo "Deploying ${SERVICE} with task definition ${TASK_DEF_ARN}"
aws ecs describe-task-definition \
  --task-definition "$TASK_DEF_ARN" \
  --query 'taskDefinition.containerDefinitions[].{name:name,image:image}' \
  --output json

update_args=(
  --cluster "$CLUSTER"
  --service "$SERVICE"
  --task-definition "$TASK_DEF_ARN"
)

if [[ -n "$DESIRED_COUNT" ]]; then
  update_args+=(--desired-count "$DESIRED_COUNT")
fi

aws ecs update-service "${update_args[@]}" > /dev/null

if [[ "${ECS_DEPLOY_WAIT_FOR_STABLE:-true}" == "true" ]]; then
  if ! python3 scripts/ci/observe_ecs_rollout.py \
    --cluster "$CLUSTER" \
    --service "$SERVICE" \
    --task-definition "$TASK_DEF_ARN" \
    --poll-seconds "${ECS_DEPLOY_POLL_SECONDS:-15}" \
    --timeout-seconds "${ECS_DEPLOY_TIMEOUT_SECONDS:-900}"; then
    echo "ECS service ${SERVICE} failed to reach stable state. Recent rollout context:" >&2
    service_context_file="$(mktemp)"
    aws ecs describe-services \
      --cluster "$CLUSTER" \
      --services "$SERVICE" \
      --output json > "$service_context_file"
    cat "$service_context_file" | jq '
        .services[0] | {
          serviceName,
          desiredCount,
          runningCount,
          pendingCount,
          deployments: [
            .deployments[] | {
              status,
              rolloutState,
              rolloutStateReason,
              taskDefinition,
              desiredCount,
              pendingCount,
              runningCount,
              failedTasks
            }
          ],
          events: [
            .events[:10][] | {
              createdAt,
              message
            }
          ]
        }
      ' >&2 || true

    stopped_tasks=$(
      aws ecs list-tasks \
        --cluster "$CLUSTER" \
        --service-name "$SERVICE" \
        --desired-status STOPPED \
        --max-items 5 \
        --query 'taskArns' \
        --output text 2>/dev/null || true
    )
    if [[ -n "$stopped_tasks" && "$stopped_tasks" != "None" ]]; then
      read -r -a stopped_task_args <<< "$stopped_tasks"
      echo "Recent stopped tasks for ${SERVICE}:" >&2
      aws ecs describe-tasks \
        --cluster "$CLUSTER" \
        --tasks "${stopped_task_args[@]}" \
        --output json | jq '
          {
            tasks: [
              .tasks[] | {
                taskArn,
                taskDefinitionArn,
                lastStatus,
                desiredStatus,
                stopCode,
                stoppedReason,
                stoppedAt,
                containers: [
                  .containers[] | {
                    name,
                    image,
                    lastStatus,
                    reason,
                    exitCode
                  }
                ]
              }
            ]
          }
        ' >&2 || true
    fi

    recent_started_task_ids=$(
      cat "$service_context_file" | jq -r '
        .services[0].events
        | map(.message | capture("\\(task (?<task_id>[0-9a-f]+)\\)"; "g").task_id? // empty)
        | flatten
        | unique
        | .[:5]
        | .[]
      ' 2>/dev/null || true
    )
    if [[ -n "$recent_started_task_ids" ]]; then
      recent_started_task_args=()
      while IFS= read -r task_id; do
        [[ -n "$task_id" ]] && recent_started_task_args+=("$task_id")
      done <<< "$recent_started_task_ids"
      echo "Recent started tasks for ${SERVICE} from service events:" >&2
      aws ecs describe-tasks \
        --cluster "$CLUSTER" \
        --tasks "${recent_started_task_args[@]}" \
        --output json | jq '
          {
            tasks: [
              .tasks[] | {
                taskArn,
                taskDefinitionArn,
                lastStatus,
                desiredStatus,
                stopCode,
                stoppedReason,
                stoppedAt,
                containers: [
                  .containers[] | {
                    name,
                    image,
                    lastStatus,
                    reason,
                    exitCode
                  }
                ]
              }
            ],
            failures
          }
        ' >&2 || true
    fi

    rm -f "$service_context_file"
    exit 1
  fi
fi

echo "Service ${SERVICE} updated to ${TASK_DEF_ARN}"
