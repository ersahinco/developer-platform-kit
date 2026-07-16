variable "stack_name" {
  description = "Stable stack prefix for starter data resources."
  type        = string
  default     = "aws-sdlc-containers"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{2,39}$", var.stack_name))
    error_message = "stack_name must be 3-40 lowercase letters, digits, or hyphens."
  }
}

variable "aws_region" {
  description = "AWS region for the object-output bucket."
  type        = string
  default     = "eu-central-1"
}

variable "export_bucket_name" {
  description = "Globally unique S3 bucket name for export objects and manifests."
  type        = string
}

variable "export_noncurrent_version_days" {
  description = "Days to retain noncurrent export-object versions."
  type        = number
  default     = 7
}

variable "export_bucket_force_destroy" {
  description = "Allow destroy to delete non-empty export buckets. Keep false outside disposable drills."
  type        = bool
  default     = false
}

variable "export_writer_user_name" {
  description = "Existing IAM user that owns the starter S3 credential lifecycle. This root grants only export-object writes."
  type        = string

  validation {
    condition     = length(trimspace(var.export_writer_user_name)) > 0
    error_message = "export_writer_user_name must identify an existing IAM user."
  }
}

variable "supabase_organization_id" {
  description = "Existing Supabase organization slug that owns the reference project."
  type        = string
}

variable "supabase_project_name" {
  description = "Supabase project display name."
  type        = string
}

variable "supabase_region" {
  description = "Supabase project region."
  type        = string
  default     = "eu-central-1"
}

variable "supabase_instance_size" {
  description = "Supabase instance size for the starter project."
  type        = string
  default     = "micro"
}

variable "supabase_database_password" {
  description = "Initial Supabase database password. Supply only through TF_VAR_supabase_database_password."
  type        = string
  sensitive   = true
}
