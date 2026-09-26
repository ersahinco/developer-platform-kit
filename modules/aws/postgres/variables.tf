variable "name" {
  description = "Instance identifier and prefix for its security and parameter groups."
  type        = string
}

variable "vpc_id" {
  description = "VPC hosting the database and client security groups."
  type        = string
}

variable "subnet_ids" {
  description = "Subnets for the database. Use the intra tier: a database needs no egress."
  type        = list(string)
}

variable "database_name" {
  description = "Initial database name."
  type        = string
}

variable "master_username" {
  description = "Master username. The password is generated and rotated by RDS."
  type        = string
  default     = "postgres"
}

variable "engine_version" {
  description = "PostgreSQL version. Pin the minor version you tested against."
  type        = string
  default     = "18.3"
}

variable "parameter_group_family" {
  description = "Parameter group family matching engine_version."
  type        = string
  default     = "postgres18"
}

variable "parameters" {
  description = "Database parameters to override."
  type        = map(string)
  default     = {}
}

variable "instance_class" {
  description = "Instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "port" {
  description = "Listening port."
  type        = number
  default     = 5432
}

variable "allocated_storage" {
  description = "Initial storage in GiB."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Storage autoscaling ceiling in GiB."
  type        = number
  default     = 100
}

variable "multi_az" {
  description = "Run a standby in a second AZ."
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "Days of automated backups. Zero disables point-in-time recovery."
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_days >= 1
    error_message = "Keep at least one day of backups. Zero disables point-in-time recovery entirely."
  }
}

variable "backup_window" {
  description = "Daily backup window in UTC."
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Weekly maintenance window in UTC."
  type        = string
  default     = "sun:04:30-sun:05:30"
}

variable "deletion_protection" {
  description = "Refuse to delete the instance through the API."
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Skip the final snapshot on destroy. Only reasonable for throwaway stacks."
  type        = bool
  default     = false
}

variable "apply_immediately" {
  description = "Apply changes now instead of in the maintenance window."
  type        = bool
  default     = false
}

variable "performance_insights_enabled" {
  description = "Enable Performance Insights."
  type        = bool
  default     = true
}

variable "kms_key_arn" {
  description = "Existing KMS key for storage and the managed secret. Null creates one."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
