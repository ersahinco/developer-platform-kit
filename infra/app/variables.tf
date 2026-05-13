variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-central-1"
}

variable "stack_name" {
  description = "Shared stack name used as the resource prefix/tag."
  type        = string
  default     = "aws-sdlc-containers"
}

variable "platform_state_bucket" {
  description = "Terraform state bucket containing the platform root state."
  type        = string
  default     = null
}

variable "platform_state_key" {
  description = "Terraform state key for platform outputs consumed by this app root."
  type        = string
  default     = null
}

# ── Edge ──────────────────────────────────────────────────────────────────────

variable "alb_ingress_cidr" {
  description = "CIDR allowed to reach the ALB on port 443. Open to 0.0.0.0/0 because HTTPS plus the fixed-token check is the access control layer."
  type        = string
  default     = "0.0.0.0/0"
}

variable "api_token_secret_name" {
  description = "Secrets Manager secret name holding the API bearer token. Create it out of band and keep it out of Terraform state and tfvars."
  type        = string
  default     = null
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

variable "data_export_job_cpu" {
  description = "Fargate task CPU units for the scheduled data export job."
  type        = number
  default     = 256
}

variable "data_export_job_memory" {
  description = "Fargate task memory (MiB) for the scheduled data export job."
  type        = number
  default     = 512
}

variable "data_export_schedule_expression" {
  description = "EventBridge Scheduler expression for the data export job."
  type        = string
  default     = "rate(1 day)"
}

variable "order_event_consumer_cpu" {
  description = "Fargate task CPU units for the order event relay/consumer service."
  type        = number
  default     = 512
}

variable "order_event_consumer_memory" {
  description = "Fargate task memory (MiB) for the order event relay/consumer service."
  type        = number
  default     = 1024
}

variable "order_event_consumer_desired_count" {
  description = "Desired number of order event relay/consumer tasks."
  type        = number
  default     = 1
}

variable "dapr_image" {
  description = "Dapr runtime sidecar image used by Dapr-enabled ECS tasks."
  type        = string
  default     = "daprio/daprd:1.17.0"
}

# ── CloudWatch app-level reduction toggles ───────────────────────────────────

variable "enable_app_symptom_cloudwatch_alarms" {
  description = "Keep CloudWatch alarms for app target 5xx and latency symptoms. Defaults true because ECS rollback uses AWS-native alarms."
  type        = bool
  default     = true
}

variable "enable_data_export_success_cloudwatch_alarm" {
  description = "Keep the CloudWatch Logs metric filter and freshness alarm for successful data exports. Defaults true until a deliberate metrics or ruler path replaces it."
  type        = bool
  default     = true
}

# ── Cloud runtime telemetry ──────────────────────────────────────────────────

variable "runtime_config_loader_image" {
  description = "Upstream AWS CLI image used as an init sidecar to copy runtime config from S3 into task-local volumes."
  type        = string
  default     = "public.ecr.aws/aws-cli/aws-cli:2.32.3"
}

variable "enable_adot_sidecar" {
  description = "Run the AWS Distro for OpenTelemetry Collector as an app-task sidecar. The app sends OTLP traces to localhost:4318 when enabled."
  type        = bool
  default     = true
}

variable "adot_collector_image" {
  description = "Pinned ADOT Collector sidecar image. Override during normal dependency refreshes."
  type        = string
  default     = "public.ecr.aws/aws-observability/aws-otel-collector:v0.47.0"
}

variable "adot_collector_config" {
  description = "Optional full ADOT Collector config. Defaults to local app metrics/traces receivers with debug export to CloudWatch logs."
  type        = string
  default     = null
}

variable "otel_exporter_otlp_traces_endpoint" {
  description = "External OTLP/HTTP traces endpoint used only when enable_adot_sidecar is false. Prefer the ADOT sidecar for ECS tasks."
  type        = string
  default     = null
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
  description = "Bootstrap app image tag for the initial task-definition revision before the app pipeline registers SHA-tagged deploy revisions."
  type        = string
  default     = "sha-7e0fa31a82d7d2a6e302e0904abb79d1dff3492d"
}

variable "app_image_tag" {
  description = "Rare operator override for the documented bootstrap app image tag. Routine app deploys and rollbacks are GitHub Actions-owned task-definition revisions."
  type        = string
  default     = null

  validation {
    condition     = var.app_image_tag == null || startswith(var.app_image_tag, "sha-")
    error_message = "app_image_tag must be null or start with sha-."
  }
}
