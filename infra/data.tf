provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

data "aws_caller_identity" "current" {}

locals {
  name       = var.stack_name
  account_id = data.aws_caller_identity.current.account_id
  # Use var.aws_region directly — data.aws_region.current.name is deprecated in aws provider v6
  region   = var.aws_region
  azs      = slice(data.aws_availability_zones.available.names, 0, var.az_count)
  api_fqdn = "api.${var.root_domain}"

  tags = {
    Project   = var.stack_name
    ManagedBy = "terraform"
  }
}

data "aws_route53_zone" "public" {
  name         = "${var.root_domain}."
  private_zone = false
}

################################################################################
# API token — read from Secrets Manager (created out-of-band, never in state).
# Run once before applying:
#   aws secretsmanager create-secret \
#     --name aws-sdlc-containers/api-token \
#     --secret-string "$(openssl rand -hex 32)"
# Or use: make create-api-token
################################################################################

data "aws_secretsmanager_secret_version" "api_token" {
  secret_id = var.api_token_secret_name
}
