output "account_id" {
  description = "AWS account ID for the platform root."
  value       = local.account_id
}

output "aws_region" {
  description = "AWS region for platform resources."
  value       = local.region
}

output "stack_name" {
  description = "Shared stack name used by platform and app roots."
  value       = local.name
}

output "root_domain" {
  description = "Public Route 53 root domain used by app-owned DNS records."
  value       = var.root_domain
}

output "route53_public_zone_id" {
  description = "Hosted zone ID for app-owned DNS records."
  value       = data.aws_route53_zone.public.zone_id
}

output "vpc_id" {
  description = "Platform VPC ID consumed by app-owned resources."
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "Platform VPC CIDR block."
  value       = var.vpc_cidr
}

output "public_subnet_ids" {
  description = "Public subnet IDs for app-owned ALB resources."
  value       = module.vpc.public_subnets
}

output "private_subnet_ids" {
  description = "Private subnet IDs for app-owned ECS resources."
  value       = module.vpc.private_subnets
}

output "intra_subnet_ids" {
  description = "Intra subnet IDs for app-owned database resources."
  value       = module.vpc.intra_subnets
}

output "github_actions_role_arn" {
  description = "GitHub Actions OIDC role ARN."
  value       = aws_iam_role.github_actions.arn
}

output "github_actions_role_name" {
  description = "GitHub Actions OIDC role name for app-scoped policy attachments."
  value       = aws_iam_role.github_actions.name
}
