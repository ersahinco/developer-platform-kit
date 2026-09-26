################################################################################
# Network
#
# One VPC with public, private, and intra subnet tiers, NAT egress, and the
# interface endpoints a private Fargate task needs to pull images, read secrets,
# and ship logs without a public route.
################################################################################

locals {
  azs = slice(var.availability_zones, 0, var.az_count)

  interface_endpoints = toset(concat(
    ["ecr.api", "ecr.dkr", "logs", "secretsmanager"],
    var.enable_ssm_exec_endpoints ? ["ssmmessages"] : [],
    var.extra_interface_endpoints,
  ))
}

module "vpc" {
  # checkov:skip=CKV_TF_1:Registry module pinned to an exact release; Terraform registry releases are versioned artifacts.
  source  = "terraform-aws-modules/vpc/aws"
  version = "6.7.3"

  name = var.name
  cidr = var.vpc_cidr
  azs  = local.azs

  private_subnets = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, 100 + i)]
  intra_subnets   = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, 200 + i)]

  enable_nat_gateway     = true
  single_nat_gateway     = var.single_nat_gateway
  one_nat_gateway_per_az = !var.single_nat_gateway

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = var.tags
}

resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.name}-vpc-endpoints-"
  description = "HTTPS from private subnets to AWS interface endpoints"
  vpc_id      = module.vpc.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  ingress {
    description = "HTTPS from inside the VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = var.tags
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.interface_endpoints

  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(var.tags, { Name = "${var.name}-${replace(each.value, ".", "-")}" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids

  tags = merge(var.tags, { Name = "${var.name}-s3" })
}
