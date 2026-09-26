variable "name" {
  description = "Load balancer name, also used as the access log prefix."
  type        = string
}

variable "vpc_id" {
  description = "VPC hosting the load balancer and its target group."
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR the load balancer may reach for targets."
  type        = string
}

variable "subnet_ids" {
  description = "Public subnets for an internet-facing ALB, private subnets for an internal one."
  type        = list(string)
}

variable "internal" {
  description = "Keep the load balancer off the internet."
  type        = bool
  default     = false
}

variable "allowed_cidr_blocks" {
  description = "Client CIDRs allowed to reach the listener."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "certificate_arn" {
  description = "ACM certificate for the HTTPS listener. Null serves HTTP only."
  type        = string
  default     = null
}

variable "allow_public_http" {
  description = "Acknowledge serving plaintext on an internet-facing load balancer."
  type        = bool
  default     = false
}

variable "ssl_policy" {
  description = "TLS policy for the HTTPS listener."
  type        = string
  default     = "ELBSecurityPolicy-TLS13-1-2-2021-06"
}

variable "target_port" {
  description = "Container port the default target group forwards to."
  type        = number
  default     = 8000
}

variable "health_check_path" {
  description = "Path the target group polls. The service must answer 200 here."
  type        = string
  default     = "/health"
}

variable "deregistration_delay" {
  description = "Seconds to drain a target before removing it."
  type        = number
  default     = 30
}

variable "idle_timeout" {
  description = "Seconds an idle connection is held open."
  type        = number
  default     = 60
}

variable "access_logs_bucket" {
  description = "S3 bucket for access logs. Null disables them."
  type        = string
  default     = null
}

variable "enable_deletion_protection" {
  description = "Refuse to delete the load balancer through the API."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
