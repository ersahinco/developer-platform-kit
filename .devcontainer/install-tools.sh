#!/usr/bin/env bash
# Pinned linters; devcontainer features supply Terraform and Docker.
set -euo pipefail

bin_dir="/usr/local/bin"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

arch="$(dpkg --print-architecture)"
case "$arch" in
  amd64)
    gitleaks_arch="x64"
    hadolint_arch="x86_64"
    ;;
  arm64)
    gitleaks_arch="arm64"
    hadolint_arch="arm64"
    ;;
  *)
    echo "Unsupported architecture: $arch" >&2
    exit 1
    ;;
esac

version="${TFLINT_VERSION:-0.62.0}"
curl -fsSL \
  "https://github.com/terraform-linters/tflint/releases/download/v${version}/tflint_linux_${arch}.zip" \
  -o "$tmp_dir/tflint.zip"
unzip -q "$tmp_dir/tflint.zip" -d "$tmp_dir/tflint"
install -m 0755 "$tmp_dir/tflint/tflint" "$bin_dir/tflint"

version="${ACTIONLINT_VERSION:-1.7.12}"
curl -fsSL \
  "https://github.com/rhysd/actionlint/releases/download/v${version}/actionlint_${version}_linux_${arch}.tar.gz" \
  -o "$tmp_dir/actionlint.tar.gz"
tar -xzf "$tmp_dir/actionlint.tar.gz" -C "$tmp_dir"
install -m 0755 "$tmp_dir/actionlint" "$bin_dir/actionlint"

version="${GITLEAKS_VERSION:-8.30.1}"
curl -fsSL \
  "https://github.com/gitleaks/gitleaks/releases/download/v${version}/gitleaks_${version}_linux_${gitleaks_arch}.tar.gz" \
  -o "$tmp_dir/gitleaks.tar.gz"
tar -xzf "$tmp_dir/gitleaks.tar.gz" -C "$tmp_dir" gitleaks
install -m 0755 "$tmp_dir/gitleaks" "$bin_dir/gitleaks"

version="${HADOLINT_VERSION:-2.14.0}"
curl -fsSL \
  "https://github.com/hadolint/hadolint/releases/download/v${version}/hadolint-Linux-${hadolint_arch}" \
  -o "$bin_dir/hadolint"
chmod 0755 "$bin_dir/hadolint"
