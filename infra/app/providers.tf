provider "aws" {
  region                      = var.aws_region
  skip_credentials_validation = true
  skip_metadata_api_check     = true
}

data "aws_caller_identity" "current" {}

data "terraform_remote_state" "platform" {
  backend = "s3"

  config = {
    bucket = local.platform_state_bucket
    key    = local.platform_state_key
    region = var.aws_region
  }
}

################################################################################
# API token - read from Secrets Manager (created out-of-band, never in state).
# Create it once before applying:
#   aws secretsmanager create-secret \
#     --name <stack-name>/api-token \
#     --secret-string "$(openssl rand -hex 32)"
# Keep the secret out of Terraform state and tfvars.
################################################################################

data "aws_secretsmanager_secret_version" "api_token" {
  secret_id = local.api_token_secret_name
}

locals {
  name       = var.stack_name
  account_id = data.aws_caller_identity.current.account_id
  region     = var.aws_region

  platform_state_bucket = coalesce(var.platform_state_bucket, "${local.name}-tfstate-${local.account_id}")
  platform_state_key    = coalesce(var.platform_state_key, "${local.name}/platform.tfstate")
  api_token_secret_name = coalesce(var.api_token_secret_name, "${local.name}/api-token")

  platform = data.terraform_remote_state.platform.outputs
  api_fqdn = "api.${local.platform.root_domain}"

  github_actions_role_arn = local.platform.github_actions_role_arn
  vpc_cidr                = local.platform.vpc_cidr

  tags = {
    Project   = var.stack_name
    ManagedBy = "terraform"
    Root      = "app"
  }
}
