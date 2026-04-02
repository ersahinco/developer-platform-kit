variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-central-1"
}

variable "environment" {
  description = "Environment name — used as a prefix/tag on all resources (e.g. dev, prod)."
  type        = string
}

variable "app_image_tag" {
  description = "ECR image tag to deploy. Set by CI using the Git commit SHA (e.g. sha-abc1234). Never 'latest'."
  type        = string
  default     = null # must be supplied explicitly — no silent fallback to latest

  validation {
    # null check must come first — null != "latest" is true in Terraform, so
    # without it a null value passes validation and fails later at apply time
    # with a confusing "Invalid template interpolation value" error.
    condition     = var.app_image_tag != null && var.app_image_tag != "latest"
    error_message = "app_image_tag must be set to a commit SHA tag (e.g. sha-abc1234). Never null or 'latest'."
  }
}

# ── Networking ────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones. 2 for non-prod, 3 for prod."
  type        = number
  default     = 2
}

variable "single_nat_gateway" {
  description = "Share one NAT Gateway across AZs (cheaper for non-prod). Set false for prod HA."
  type        = bool
  default     = true
}

# ── ECS ───────────────────────────────────────────────────────────────────────

variable "app_cpu" {
  description = "Fargate task CPU units for the app service (256, 512, 1024, 2048, 4096)."
  type        = number
  default     = 512
}

variable "app_memory" {
  description = "Fargate task memory (MiB) for the app service."
  type        = number
  default     = 1024
}

variable "app_desired_count" {
  description = "Desired number of running app tasks."
  type        = number
  default     = 1
}

variable "pgbouncer_pool_size" {
  description = "PgBouncer default_pool_size — server-side connections to RDS per database. Set to ~80% of RDS max_connections divided by expected task count."
  type        = number
  default     = 20
}

variable "worker_cpu" {
  description = "Fargate task CPU units for the one-off backfill worker."
  type        = number
  default     = 256
}

variable "worker_memory" {
  description = "Fargate task memory (MiB) for the one-off backfill worker."
  type        = number
  default     = 512
}

variable "backfill_batch_size" {
  description = "Number of rows per backfill batch."
  type        = number
  default     = 1000
}

# ── RDS ───────────────────────────────────────────────────────────────────────

variable "rds_instance_class" {
  description = "RDS instance class. db.t4g.small for dev/staging, db.t4g.medium for prod."
  type        = string
  default     = "db.t4g.small"
}

variable "rds_multi_az" {
  description = "Enable Multi-AZ standby for RDS. Also enables deletion_protection and final snapshot."
  type        = bool
  default     = false
}

variable "rds_allocated_storage_gb" {
  description = "Initial RDS storage in GB. Autoscales up to 5× this value."
  type        = number
  default     = 20
}
