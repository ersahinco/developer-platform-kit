#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE=${GITHUB_OUTPUT:-}
AWS_REGION=${AWS_REGION:-eu-central-1}

account_id=$(aws sts get-caller-identity --query Account --output text)
ecr_registry="${account_id}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "Resolved account: ${account_id}"
echo "Resolved ECR registry: ${ecr_registry}"

if [[ -n "$OUTPUT_FILE" ]]; then
  {
    echo "account_id=${account_id}"
    echo "ecr_registry=${ecr_registry}"
  } >> "$OUTPUT_FILE"
fi
