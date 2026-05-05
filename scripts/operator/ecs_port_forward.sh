#!/usr/bin/env bash
# ecs_port_forward.sh — SSM port-forward to a container in an ECS Exec-enabled task.
# Usage: ecs_port_forward.sh <cluster> <service> <container> <remote_port> <local_port> <aws_region>
set -euo pipefail

CLUSTER=$1
SERVICE=$2
CONTAINER=$3
REMOTE_PORT=$4
LOCAL_PORT=$5
AWS_REGION=$6

echo "-> waiting for $CLUSTER/$SERVICE to become stable"
aws ecs wait services-stable \
  --cluster "$CLUSTER" \
  --services "$SERVICE" \
  --region "$AWS_REGION"

for attempt in $(seq 1 30); do
  TASK_ARNS=$(aws ecs list-tasks \
    --cluster "$CLUSTER" \
    --service-name "$SERVICE" \
    --desired-status RUNNING \
    --query 'taskArns' \
    --output text \
    --region "$AWS_REGION")

  if [ -n "$TASK_ARNS" ] && [ "$TASK_ARNS" != "None" ]; then
    TARGET=$(aws ecs describe-tasks \
      --cluster "$CLUSTER" \
      --tasks $TASK_ARNS \
      --region "$AWS_REGION" \
      --output json \
      | python3 -c '
import json
import sys

container_name = sys.argv[1]
payload = json.load(sys.stdin)

for task in sorted(payload.get("tasks", []), key=lambda item: item.get("startedAt", ""), reverse=True):
    if task.get("lastStatus") != "RUNNING":
        continue
    if task.get("desiredStatus") != "RUNNING":
        continue
    if not task.get("enableExecuteCommand"):
        continue

    for container in task.get("containers", []):
        if container.get("name") != container_name:
            continue
        if container.get("lastStatus") != "RUNNING":
            continue
        agents = container.get("managedAgents", [])
        exec_agent_running = any(
            agent.get("name") == "ExecuteCommandAgent"
            and agent.get("lastStatus") == "RUNNING"
            for agent in agents
        )
        if exec_agent_running and container.get("runtimeId"):
            print("{} {}".format(task.get("taskArn"), container.get("runtimeId")))
            raise SystemExit(0)

raise SystemExit(1)
' "$CONTAINER" || true)

    if [ -n "$TARGET" ]; then
      TASK_ARN=$(echo "$TARGET" | awk '{print $1}')
      RUNTIME_ID=$(echo "$TARGET" | awk '{print $2}')
      TASK_ID=$(echo "$TASK_ARN" | awk -F/ '{print $NF}')

      echo "-> tunnel http://127.0.0.1:$LOCAL_PORT -> $CONTAINER.$CLUSTER.local:$REMOTE_PORT via task $TASK_ID"
      aws ssm start-session \
        --target "ecs:${CLUSTER}_${TASK_ID}_${RUNTIME_ID}" \
        --document-name AWS-StartPortForwardingSession \
        --parameters "{\"portNumber\":[\"$REMOTE_PORT\"],\"localPortNumber\":[\"$LOCAL_PORT\"]}" \
        --region "$AWS_REGION"
      exit $?
    fi
  fi

  echo "-> waiting for ExecuteCommandAgent in $SERVICE/$CONTAINER ($attempt/30)"
  sleep 2
done

echo "ERROR: no connected ECS Exec target found for $CLUSTER/$SERVICE container $CONTAINER" >&2
exit 1
