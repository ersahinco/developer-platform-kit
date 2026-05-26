#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 <workflow-file> <ref> <head-sha> [gh workflow run flags...]" >&2
}

if [[ $# -lt 3 ]]; then
  usage
  exit 2
fi

workflow_file="$1"
ref="$2"
head_sha="$3"
shift 3

dispatch_started_epoch="$(date +%s)"

gh workflow run "$workflow_file" --ref "$ref" "$@"

run_id=""
deadline=$((SECONDS + 300))
while (( SECONDS < deadline )); do
  run_json="$(
    gh run list \
      --workflow "$workflow_file" \
      --event workflow_dispatch \
      --branch "$ref" \
      --commit "$head_sha" \
      --limit 20 \
      --json databaseId,createdAt,status,conclusion,url \
      --jq \
        '[.[] | select((.createdAt | fromdateiso8601) >= '"${dispatch_started_epoch}"')] | sort_by(.createdAt) | last'
  )"
  if [[ -n "$run_json" && "$run_json" != "null" ]]; then
    run_id="$(jq -r '.databaseId' <<<"$run_json")"
    break
  fi
  sleep 3
done

if [[ -z "$run_id" ]]; then
  echo "Could not resolve workflow_dispatch run for ${workflow_file} on ${ref} (${head_sha})." >&2
  exit 1
fi

gh run watch "$run_id" --exit-status --interval 5
echo "$run_id"
