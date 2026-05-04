#!/usr/bin/env bash
# grafana_tunnel.sh — SSM port-forward localhost:LOCAL_PORT → private Grafana:3000
# Usage: grafana_tunnel.sh <local_port> <aws_region>
set -euo pipefail

LOCAL_PORT=${1:-3000}
AWS_REGION=${2:-eu-central-1}

cd "$(dirname "$0")/.."

cd infra/app
terraform init \
  -backend-config="key=aws-sdlc-containers/app.tfstate" \
  -reconfigure -input=false > /dev/null 2>&1

CLUSTER=$(terraform output -raw ecs_cluster_name)
SERVICE=$(terraform output -raw observability_grafana_service_name)
cd ../..

[ -n "$SERVICE" ] && [ "$SERVICE" != "null" ] \
  || { echo "ERROR: observability Grafana service is not enabled"; exit 1; }

echo "   Open Grafana at: http://127.0.0.1:$LOCAL_PORT"

bash scripts/ecs_port_forward.sh "$CLUSTER" "$SERVICE" grafana 3000 "$LOCAL_PORT" "$AWS_REGION"
