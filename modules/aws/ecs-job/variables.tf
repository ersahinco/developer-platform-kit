variable "name" {
  description = "Job name, task family, and prefix for its roles."
  type        = string
}

variable "cluster_id" {
  description = "ECS cluster ARN the job runs in."
  type        = string
}

variable "image" {
  description = "Initial image. The task lane may override it per run."
  type        = string
}

variable "container_name" {
  description = "Container name the task lane targets for overrides and log streams."
  type        = string
  default     = "job"
}

variable "command" {
  description = "Default command. Null uses the image entrypoint."
  type        = list(string)
  default     = null
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
  description = "X86_64 or ARM64."
  type        = string
  default     = "X86_64"
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

variable "vpc_id" {
  description = "VPC hosting the task security group."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets for the task."
  type        = list(string)
}

variable "schedule_expression" {
  description = "EventBridge Scheduler expression, e.g. \"cron(0 2 * * ? *)\". Null makes this an operator job."
  type        = string
  default     = null
}

variable "schedule_timezone" {
  description = "Timezone for the schedule expression."
  type        = string
  default     = "UTC"
}

variable "schedule_enabled" {
  description = "Whether the schedule fires. Disable to pause without deleting."
  type        = bool
  default     = true
}

variable "schedule_retry_attempts" {
  description = "Retries when the scheduler cannot start the task. Not a retry of a failed run."
  type        = number
  default     = 0
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
