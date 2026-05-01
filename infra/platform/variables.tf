variable "aws_region" {
  description = "AWS region for platform resources."
  type        = string
  default     = "eu-central-1"
}

variable "stack_name" {
  description = "Shared stack name used as the resource prefix/tag across platform and app roots."
  type        = string
  default     = "aws-sdlc-containers"
}

variable "root_domain" {
  description = "Public Route 53 root domain registered in this AWS account."
  type        = string
}

variable "az_count" {
  description = "Number of availability zones to use for subnet groups."
  type        = number
  default     = 2
}

variable "vpc_cidr" {
  description = "CIDR block for the platform VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "single_nat_gateway" {
  description = "Share one NAT Gateway across all subnets to keep the stack lean."
  type        = bool
  default     = true
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the CI role through OIDC, in owner/name form."
  type        = string
  default     = "ersahinco/aws-sdlc-containers"
}
