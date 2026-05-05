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
  default     = "aws-sdlc-containers-tfstate-691627364817"
}

variable "platform_state_key" {
  description = "Terraform state key for platform outputs consumed by this app root."
  type        = string
  default     = "aws-sdlc-containers/platform.tfstate"
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
  default     = "aws-sdlc-containers/api-token"
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
  description = "Keep CloudWatch alarms for app target 5xx and latency symptoms. Defaults true; set false only after deployed Grafana-stack alerts have dual-run successfully."
  type        = bool
  default     = true
}

variable "enable_data_export_success_cloudwatch_alarm" {
  description = "Keep the CloudWatch Logs metric filter and freshness alarm for successful data exports. Defaults true; set false only after a Grafana-stack data export freshness signal has dual-run successfully."
  type        = bool
  default     = true
}

# ── Optional ECS Grafana stack ────────────────────────────────────────────────

variable "enable_observability_stack" {
  description = "Deploy the optional ECS/Fargate Grafana, Loki, and Prometheus stack. Defaults to false so the base plan remains unchanged."
  type        = bool
  default     = false
}

variable "grafana_admin_secret_name" {
  description = "Secrets Manager secret name holding the Grafana admin password. Create this out of band before enabling the observability stack."
  type        = string
  default     = "aws-sdlc-containers/grafana-admin"
}

variable "observability_config_loader_image" {
  description = "Upstream AWS CLI image used as an init sidecar to copy observability config from S3 into task-local volumes."
  type        = string
  default     = "public.ecr.aws/aws-cli/aws-cli:2.32.3"
}

variable "grafana_image" {
  description = "Upstream Grafana image for the optional observability stack."
  type        = string
  default     = "grafana/grafana:13.0.1"
}

variable "loki_image" {
  description = "Upstream Loki image for the optional observability stack."
  type        = string
  default     = "grafana/loki:3.6.10"
}

variable "prometheus_image" {
  description = "Upstream Prometheus image for the optional observability stack."
  type        = string
  default     = "prom/prometheus:v3.11.2"
}

variable "tempo_image" {
  description = "Upstream Tempo image for the optional self-hosted traces stack."
  type        = string
  default     = "grafana/tempo:2.9.0"
}

variable "firelens_image_tag" {
  description = "FireLens image tag built from observability/firelens and pushed to ECR."
  type        = string
  default     = "sha-23f61d05d3a0e2f55def6fcdd2b64ce761817963"
}

variable "grafana_cpu" {
  description = "Fargate task CPU units for the optional Grafana service."
  type        = number
  default     = 256
}

variable "grafana_memory" {
  description = "Fargate task memory (MiB) for the optional Grafana service."
  type        = number
  default     = 512
}

variable "loki_cpu" {
  description = "Fargate task CPU units for the optional Loki service."
  type        = number
  default     = 512
}

variable "loki_memory" {
  description = "Fargate task memory (MiB) for the optional Loki service."
  type        = number
  default     = 1024
}

variable "prometheus_cpu" {
  description = "Fargate task CPU units for the optional Prometheus service."
  type        = number
  default     = 512
}

variable "prometheus_memory" {
  description = "Fargate task memory (MiB) for the optional Prometheus service."
  type        = number
  default     = 1024
}

variable "tempo_cpu" {
  description = "Fargate task CPU units for the optional Tempo service."
  type        = number
  default     = 512
}

variable "tempo_memory" {
  description = "Fargate task memory (MiB) for the optional Tempo service."
  type        = number
  default     = 1024
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

variable "app_image_tag" {
  description = "Optional app image tag to keep Terraform aligned with the currently deployed app revision without changing support workload image tags."
  type        = string
  default     = null

  validation {
    condition     = var.app_image_tag == null || startswith(var.app_image_tag, "sha-")
    error_message = "app_image_tag must be null or start with sha-."
  }
}
