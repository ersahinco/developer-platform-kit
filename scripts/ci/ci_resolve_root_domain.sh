#!/usr/bin/env bash
set -euo pipefail

TFVARS_PATH=${1:-infra/platform/stack.tfvars}

resolve_from_tfvars() {
  local path=$1
  [[ -f "$path" ]] || return 1
  awk -F'"' '/^[[:space:]]*root_domain[[:space:]]*=/ {print $2; exit}' "$path"
}

root_domain=${ROOT_DOMAIN:-}
if [[ -z "$root_domain" ]]; then
  root_domain=$(resolve_from_tfvars "$TFVARS_PATH" || true)
fi

if [[ -z "$root_domain" ]]; then
  echo "Set ROOT_DOMAIN or declare root_domain in ${TFVARS_PATH} before continuing." >&2
  exit 1
fi

if [[ -n "${GITHUB_ENV:-}" ]]; then
  echo "ROOT_DOMAIN=${root_domain}" >> "$GITHUB_ENV"
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "root_domain=${root_domain}" >> "$GITHUB_OUTPUT"
fi

printf '%s\n' "$root_domain"
