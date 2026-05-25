#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG=${1:?"usage: ci_validate_image_tag.sh <image-tag> <default-branch>"}
DEFAULT_BRANCH=${2:?"usage: ci_validate_image_tag.sh <image-tag> <default-branch>"}
REQUIRE_ROOT_DOMAIN=${CI_REQUIRE_ROOT_DOMAIN:-false}

if [[ "$REQUIRE_ROOT_DOMAIN" == "true" && -z "${ROOT_DOMAIN:-}" ]]; then
  echo "Set ROOT_DOMAIN as a GitHub repository or environment variable before continuing." >&2
  exit 1
fi

if [[ ! "$IMAGE_TAG" =~ ^sha-[0-9a-f]{40}$ ]]; then
  echo "image_tag must be sha- followed by a 40-character lowercase commit SHA." >&2
  exit 1
fi

image_sha="${IMAGE_TAG#sha-}"
if ! git merge-base --is-ancestor "$image_sha" "origin/${DEFAULT_BRANCH}"; then
  echo "image_tag must reference a commit reachable from ${DEFAULT_BRANCH}." >&2
  exit 1
fi
