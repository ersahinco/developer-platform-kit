#!/usr/bin/env bash
# tls_import.sh ENV REGION
#
# Generates a self-signed TLS certificate for the ALB's built-in DNS name,
# imports it into ACM, and writes the ARN to infra/.tls-cert-arn-ENV.
#
# Terraform reads that file via file() — the ARN never touches state or tfvars.
# Callers must pass --insecure / -k when hitting the HTTPS endpoint.
#
# Idempotent: exits early if infra/.tls-cert-arn-ENV already exists.
# To rotate: delete infra/.tls-cert-arn-ENV and re-run.

set -euo pipefail

ENV="${1:?usage: tls_import.sh ENV REGION}"
REGION="${2:?usage: tls_import.sh ENV REGION}"
ARN_FILE="infra/.tls-cert-arn-${ENV}"

if [[ -f "$ARN_FILE" ]]; then
  echo "Certificate ARN file $ARN_FILE already exists — skipping."
  echo "Delete it and re-run to rotate the certificate."
  exit 0
fi

# Resolve the ALB DNS name from AWS directly — avoids requiring terraform output
# (which needs backend init) and works immediately after the ALB is created.
echo "--- Resolving ALB DNS name for ${ENV} ---"
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --region "$REGION" \
  --query "LoadBalancers[?LoadBalancerName=='db-migration-example-${ENV}'].DNSName | [0]" \
  --output text)

if [[ -z "$ALB_DNS" || "$ALB_DNS" == "None" ]]; then
  echo "ERROR: could not find ALB 'db-migration-example-${ENV}' in ${REGION}."
  echo "Apply the ALB resources first: make infra-apply-${ENV}"
  exit 1
fi
echo "ALB DNS: ${ALB_DNS}"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

CERT_FILE="${TMPDIR}/cert.pem"
KEY_FILE="${TMPDIR}/key.pem"

echo "--- Generating self-signed certificate (CN=${ALB_DNS}) ---"
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$KEY_FILE" \
  -out    "$CERT_FILE" \
  -days   825 \
  -subj   "/CN=alb-self-signed" \
  -addext "subjectAltName=DNS:${ALB_DNS}" \
  2>/dev/null

echo "--- Importing certificate into ACM (${REGION}) ---"
CERT_ARN=$(aws acm import-certificate \
  --certificate  fileb://"$CERT_FILE" \
  --private-key  fileb://"$KEY_FILE" \
  --region       "$REGION" \
  --tags         Key=Project,Value=db-migration-example Key=Environment,Value="$ENV" Key=ManagedBy,Value=make \
  --query        'CertificateArn' \
  --output       text)

echo "Certificate ARN: ${CERT_ARN}"
echo -n "$CERT_ARN" > "$ARN_FILE"
echo "Written to ${ARN_FILE} — Terraform will read this on next apply."
