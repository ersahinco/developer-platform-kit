variable "name" {
  description = "Application name and prefix for its role and log group."
  type        = string
}

variable "release_label" {
  description = "EMR release. Pin the version your job was tested against."
  type        = string
  default     = "emr-7.5.0"
}

variable "architecture" {
  description = "X86_64 or ARM64."
  type        = string
  default     = "ARM64"
}

variable "maximum_cpu" {
  description = "Ceiling on concurrent vCPU, e.g. \"64 vCPU\". A runaway job stops here."
  type        = string
  default     = "32 vCPU"
}

variable "maximum_memory" {
  description = "Ceiling on concurrent memory, e.g. \"256 GB\"."
  type        = string
  default     = "128 GB"
}

variable "idle_timeout_minutes" {
  description = "Minutes of idleness before the application stops and stops billing."
  type        = number
  default     = 15
}

variable "vpc_id" {
  description = "VPC for the job security group. Only needed when subnet_ids is set."
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "Private subnets for jobs that reach VPC resources. Empty keeps jobs outside the VPC."
  type        = list(string)
  default     = []
}

variable "data_bucket_names" {
  description = "Buckets the jobs may read and write: job code, raw, curated, reports."
  type        = list(string)

  validation {
    condition     = length(var.data_bucket_names) > 0
    error_message = "A Spark job with no bucket access cannot read input or write output."
  }
}

variable "glue_catalog_access" {
  description = "Allow the jobs to read and register tables in the Glue Data Catalog."
  type        = bool
  default     = true
}

variable "additional_job_policy_json" {
  description = "Extra inline policies for the job role, keyed by policy name."
  type        = map(string)
  default     = {}
}

variable "log_retention_days" {
  description = "Retention for the job log group."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
