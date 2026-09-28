variable "name" {
  description = "Service name, task family, and prefix for its roles."
  type        = string
}

variable "cluster_id" {
  description = "ECS cluster ARN."
  type        = string
}

variable "image" {
  description = "Initial image. The deploy lane owns it after creation, so a placeholder is fine."
  type        = string
}

variable "container_name" {
  description = "Container name the deploy lane targets when it swaps the image."
  type        = string
  default     = "app"
}

variable "container_port" {
  description = "Port the container listens on. Null for a service with no inbound traffic."
  type        = number
  default     = 8000
}

variable "cpu" {
  description = "Task CPU units."
  type        = number
  default     = 512
}

variable "memory" {
  description = "Task memory in MiB."
  type        = number
  default     = 1024
}

variable "cpu_architecture" {
  description = "X86_64 or ARM64. ARM64 is cheaper when the image supports it."
  type        = string
  default     = "X86_64"
}

variable "desired_count" {
  description = "Task count managed by this module."
  type        = number
  default     = 2
}

variable "environment" {
  description = "Plain configuration passed as environment variables."
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Secret environment variables, mapping variable name to Secrets Manager or SSM ARN."
  type        = map(string)
  default     = {}
}

variable "health_check_command" {
  description = "Container health check command, e.g. [\"CMD-SHELL\", \"curl -f localhost:8000/ready\"]."
  type        = list(string)
  default     = null
}

variable "vpc_id" {
  description = "VPC hosting the task security group."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets for the tasks."
  type        = list(string)
}

variable "load_balancer_security_group_id" {
  description = "Load balancer security group allowed to reach the container port."
  type        = string
  default     = null
}

variable "ingress_security_group_ids" {
  description = "Peer security groups allowed to reach the container port."
  type        = list(string)
  default     = []
}

variable "extra_security_group_ids" {
  description = "Additional security groups attached to the tasks, e.g. a database client group."
  type        = list(string)
  default     = []
}

variable "target_group_arn" {
  description = "Target group to register with. Null keeps the service off the load balancer."
  type        = string
  default     = null
}

variable "capacity_provider" {
  description = "Capacity provider, e.g. FARGATE_SPOT. Null uses the FARGATE launch type."
  type        = string
  default     = null
}

variable "deployment_minimum_healthy_percent" {
  description = "Minimum healthy percent during a rollout."
  type        = number
  default     = 100
}

variable "deployment_maximum_percent" {
  description = "Maximum percent of desired count during a rollout."
  type        = number
  default     = 200
}

variable "health_check_grace_period_seconds" {
  description = "Grace period before load balancer health checks count against a new task."
  type        = number
  default     = 60
}

variable "enable_execute_command" {
  description = "Allow ECS Exec into the running task. Audit trail lives in CloudTrail."
  type        = bool
  default     = false
}

variable "task_policy_json" {
  description = "Inline runtime policies for the task role, keyed by policy name."
  type        = map(string)
  default     = {}
}

variable "task_policy_arns" {
  description = "Managed policies attached to the task role, keyed by a review-friendly name."
  type        = map(string)
  default     = {}
}

variable "log_group_name" {
  description = "Log group name. Null uses /ecs/<name>."
  type        = string
  default     = null
}

variable "log_retention_days" {
  description = "Log retention in days."
  type        = number
  default     = 30
}

variable "log_kms_key_arn" {
  description = "KMS key for log encryption. Null uses the CloudWatch default."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
