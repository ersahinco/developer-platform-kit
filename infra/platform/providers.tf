provider "aws" {
  region                      = var.aws_region
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
}

data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

data "aws_caller_identity" "current" {}

data "aws_route53_zone" "public" {
  name         = "${var.root_domain}."
  private_zone = false
}

locals {
  name       = var.stack_name
  account_id = data.aws_caller_identity.current.account_id
  region     = var.aws_region
  azs        = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  tags = {
    Project   = var.stack_name
    ManagedBy = "terraform"
    Root      = "platform"
  }
}
