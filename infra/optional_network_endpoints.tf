################################################################################
# Optional networking features
#
# These endpoints keep ECS traffic on the AWS network and reduce dependence on
# the NAT Gateway, but they are not required for the lean base stack itself.
# They stay enabled by default in this phase so the deployed behavior is
# unchanged while the boundaries become explicit.
################################################################################

resource "aws_security_group" "vpc_endpoints" {
  # name_prefix + create_before_destroy: same reason as alb SG — description
  # changes force replacement and a fixed name collides in the same VPC.
  name_prefix = "${local.name}-vpc-endpoints-"
  description = "Allow HTTPS from private subnets to AWS Interface Endpoints"
  vpc_id      = module.vpc.vpc_id

  lifecycle {
    create_before_destroy = true
  }

  ingress {
    description = "HTTPS from ECS tasks"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = local.tags
}

# ECR API — image manifest and auth calls
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${local.region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-ecr-api" })
}

# ECR DKR — image layer pulls
resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${local.region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-ecr-dkr" })
}

# Secrets Manager — DB password injection at task startup
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${local.region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-secretsmanager" })
}

# CloudWatch Logs — container log delivery from awslogs driver
resource "aws_vpc_endpoint" "logs" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${local.region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-logs" })
}

# S3 Gateway Endpoint — ECR stores image layers in S3; Gateway endpoints are free
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${local.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids
  tags              = merge(local.tags, { Name = "${local.name}-s3" })
}

# SSM Messages — required for ECS Exec (db-tunnel, db-exec) and SSM Session
# Manager. This stays alongside the other optional endpoint resources because it
# is only needed when ECS Exec support is enabled.
resource "aws_vpc_endpoint" "ssmmessages" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${local.region}.ssmmessages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-ssmmessages" })
}
