#!/usr/bin/env bash
# Exercise the real Compose service and native PostgreSQL TLS configuration.
set -euo pipefail
export TEST_CERTS
TEST_CERTS=$(mktemp -d)
project="dpk-hosting-check-$$"
compose=(docker compose -p "$project" -f tests/hosting/compose.yaml)
cleanup() {
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$TEST_CERTS"
}
trap cleanup EXIT
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -keyout "$TEST_CERTS/server.key" -out "$TEST_CERTS/server.crt" \
  -subj /CN=postgres -addext subjectAltName=DNS:postgres >/dev/null 2>&1
# PostgreSQL reads the public certificate as its own user on Linux bind mounts.
chmod 755 "$TEST_CERTS"
chmod 644 "$TEST_CERTS/server.crt"
export TEST_DATABASE_CA
TEST_DATABASE_CA=$(cat "$TEST_CERTS/server.crt")
export PORTAL_IMAGE
PORTAL_IMAGE=$(cat platform/.local/check-image-id)
"${compose[@]}" up --abort-on-container-exit --exit-code-from backstage
