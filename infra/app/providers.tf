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
# Primary edge token - created out-of-band and injected into the workload at
# runtime.
# Create it once before applying:
#   aws secretsmanager create-secret \
#     --name <stack-name>/edge-token \
#     --secret-string "$(openssl rand -hex 32)"
# Terraform keeps only the secret identifier so plan does not need the payload.
################################################################################

locals {
  name       = var.stack_name
  account_id = data.aws_caller_identity.current.account_id
  region     = var.aws_region

  platform_state_bucket = coalesce(var.platform_state_bucket, "${local.name}-tfstate-${local.account_id}")
  platform_state_key    = coalesce(var.platform_state_key, "${local.name}/platform.tfstate")
  primary_edge_auth_token_secret_name = coalesce(
    var.primary_edge_auth_token_secret_name,
    "${local.name}/edge-token"
  )
  primary_edge_hostname_label = coalesce(
    var.primary_edge_hostname_label,
    try(local.workloads_by_name[local.primary_edge_workload_name].edge.hostname_label, null),
    local.workloads_by_name[local.primary_edge_workload_name].image.repository
  )

  platform          = data.terraform_remote_state.platform.outputs
  primary_edge_fqdn = "${local.primary_edge_hostname_label}.${local.platform.root_domain}"

  github_actions_role_arn = local.platform.github_actions_role_arn
  vpc_cidr                = local.platform.vpc_cidr

  tags = {
    Project   = var.stack_name
    ManagedBy = "terraform"
    Root      = "app"
  }
}
