#!/usr/bin/env bash
# loki_tunnel.sh — SSM port-forward localhost:LOCAL_PORT → private Loki:3100
# Usage: loki_tunnel.sh <local_port> <aws_region>
set -euo pipefail

LOCAL_PORT=${1:-3100}
AWS_REGION=${2:-eu-central-1}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$ROOT_DIR"

cd infra/app
terraform init \
  -backend-config="key=aws-sdlc-containers/app.tfstate" \
  -reconfigure -input=false > /dev/null 2>&1

CLUSTER=$(terraform output -raw ecs_cluster_name)
SERVICE=$(terraform output -raw observability_loki_service_name)
cd ../..

[ -n "$SERVICE" ] && [ "$SERVICE" != "null" ] \
  || { echo "ERROR: observability Loki service is not enabled"; exit 1; }

echo "   Verify Loki with: LOKI_URL=http://127.0.0.1:$LOCAL_PORT make observability-delivery-verify"

bash scripts/operator/ecs_port_forward.sh "$CLUSTER" "$SERVICE" loki 3100 "$LOCAL_PORT" "$AWS_REGION"
