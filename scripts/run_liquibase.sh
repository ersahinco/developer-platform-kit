#!/usr/bin/env bash
# run_liquibase.sh — thin wrapper that passes the given action to the Liquibase Docker container.
# Usage: ./scripts/run_liquibase.sh <action>   e.g. update, validate, rollbackCount 1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

docker compose --profile migration -f "${SCRIPT_DIR}/../docker-compose.yml" run --rm liquibase "$@"
