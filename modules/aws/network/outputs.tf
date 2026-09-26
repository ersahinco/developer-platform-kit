output "vpc_id" {
  description = "VPC ID."
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "VPC CIDR block."
  value       = var.vpc_cidr
}

output "public_subnet_ids" {
  description = "Public subnets, for internet-facing load balancers only."
  value       = module.vpc.public_subnets
}

output "private_subnet_ids" {
  description = "Private subnets with NAT egress, for tasks."
  value       = module.vpc.private_subnets
}

output "intra_subnet_ids" {
  description = "Subnets with no egress route, for databases."
  value       = module.vpc.intra_subnets
}

output "availability_zones" {
  description = "Availability zones in use."
  value       = local.azs
}
