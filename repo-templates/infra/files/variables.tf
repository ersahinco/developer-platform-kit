variable "stack_name" {
  description = "Stack name. Prefixes every resource name."
  type        = string
}

variable "aws_region" {
  description = "Region the stack lives in."
  type        = string
}

variable "environment" {
  description = "Environment label passed to workloads and used in logs."
  type        = string
}

variable "state_bucket" {
  description = "Terraform state bucket the delivery role may access."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the stack VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "single_nat_gateway" {
  description = "Share one NAT gateway across AZs."
  type        = bool
  default     = true
}

variable "certificate_arn" {
  description = "ACM certificate for the public listener. Null serves HTTP only."
  type        = string
  default     = null
}

variable "edge_target_port" {
  description = "Container port the default target group forwards to."
  type        = number
  default     = 8000
}

variable "database_name" {
  description = "Initial database name."
  type        = string
  default     = "app"
}

variable "database_multi_az" {
  description = "Run a database standby in a second AZ."
  type        = bool
  default     = false
}

variable "log_level" {
  description = "Log level passed to every workload."
  type        = string
  default     = "INFO"
}

variable "services" {
  description = <<-EOT
    Services in this stack, keyed by workload name. The key becomes the ECR
    repository, ECS service, and task family name, so it must match what the
    workload repo's deploy lane passes.
  EOT
  type = map(object({
    container_port = optional(number, 8000)
    cpu            = optional(number, 512)
    memory         = optional(number, 1024)
    desired_count  = optional(number, 2)
    public         = optional(bool, false)
    needs_database = optional(bool, false)
    environment    = optional(map(string), {})
    secrets        = optional(map(string), {})
  }))
  default = {}

  validation {
    condition     = length([for name, _ in var.services : name if length(name) > 40]) == 0
    error_message = "Service names must be 40 characters or fewer: they become load balancer target group and IAM role names."
  }
  validation {
    condition     = length([for service in values(var.services) : service if service.public]) <= 1
    error_message = "This starter has one ALB target group. Use at most one public service; add explicit routing before adding another."
  }
}

variable "data_pipelines" {
  description = <<-EOT
    Data pipelines in this stack, keyed by pipeline name. Each one gets a
    migration task family named <pipeline>-migrations and an ECR repository to
    match, so the key must equal PIPELINE_NAME in the data repo.
  EOT
  type = map(object({
    description = optional(string, "")
  }))
  default = {}
}

variable "delivery_policy_arns" {
  description = "Managed policies the CI delivery role needs, keyed by a review-friendly name."
  type        = map(string)
  default     = {}
}

variable "allow_public_http" {
  description = "Explicitly allow an unencrypted public listener for a development stack."
  type        = bool
  default     = false
}
