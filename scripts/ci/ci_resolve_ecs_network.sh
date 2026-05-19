#!/usr/bin/env bash
set -euo pipefail

STACK_NAME=${1:?"usage: ci_resolve_ecs_network.sh <stack-name>"}
OUTPUT_FILE=${GITHUB_OUTPUT:-}

SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=${STACK_NAME}-private-*" \
  --query 'Subnets[0].SubnetId' \
  --output text)

SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=${STACK_NAME}-api-*" \
  --query 'SecurityGroups[0].GroupId' \
  --output text)

if [ -z "$SUBNET_ID" ] || [ "$SUBNET_ID" = "None" ]; then
  echo "Failed to resolve private subnet for stack ${STACK_NAME}" >&2
  exit 1
fi

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  echo "Failed to resolve api security group for stack ${STACK_NAME}" >&2
  exit 1
fi

echo "Resolved subnet: ${SUBNET_ID}"
echo "Resolved security group: ${SG_ID}"

if [ -n "$OUTPUT_FILE" ]; then
  {
    echo "subnet_id=${SUBNET_ID}"
    echo "sg_id=${SG_ID}"
  } >> "$OUTPUT_FILE"
fi
