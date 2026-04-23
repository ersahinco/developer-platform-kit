variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-central-1"
}

variable "stack_name" {
  description = "Single stack name used as the resource prefix/tag across the project."
  type        = string
  default     = "aws-sdlc-containers"
}


# ── Networking ────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "alb_ingress_cidr" {
  description = "CIDR allowed to reach the ALB on port 443. Open to 0.0.0.0/0 because HTTPS plus the fixed-token check is the access control layer."
  type        = string
  default     = "0.0.0.0/0"
}

variable "api_token_secret_name" {
  description = "Secrets Manager secret name holding the API bearer token. Create it out of band and keep it out of Terraform state and tfvars."
  type        = string
  default     = "aws-sdlc-containers/api-token"
}

variable "root_domain" {
  description = "Public Route 53 root domain registered in this AWS account (for example: example-sandbox.click). The API hostname is created as api.<root_domain>."
  type        = string
}

variable "az_count" {
  description = "Number of availability zones to use for subnet groups. Keep 2 for a lean setup; RDS subnet groups require at least 2 AZs even when the DB instance itself is single-AZ."
  type        = number
  default     = 2
}

variable "single_nat_gateway" {
  description = "Share one NAT Gateway across all subnets to keep the stack lean."
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
  description = "RDS instance class for the single PostgreSQL instance."
  type        = string
  default     = "db.t4g.small"
}

variable "rds_multi_az" {
  description = "Enable Multi-AZ standby for RDS. Defaults to false because this project intentionally uses a lean single-AZ database."
  type        = bool
  default     = false
}

variable "rds_allocated_storage_gb" {
  description = "Initial RDS storage in GB. Autoscales up to 5× this value."
  type        = number
  default     = 20
}

variable "initial_image_tag" {
  description = "Image tag used in task definitions on first apply. CI always registers a new task definition revision with the real SHA before deploying or running one-off tasks — this value is never used after the first apply."
  type        = string
  default     = "sha-7e0fa31a82d7d2a6e302e0904abb79d1dff3492d"
}
