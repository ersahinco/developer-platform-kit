variable "name" {
  description = "IAM role name for this delivery lane."
  type        = string
}

variable "github_repository" {
  description = "Repository allowed to assume the role, as owner/name."
  type        = string

  validation {
    condition     = can(regex("^[^/]+/[^/]+$", var.github_repository))
    error_message = "github_repository must be owner/name, with exactly one slash."
  }
}

variable "environments" {
  description = "GitHub environments allowed to assume the role."
  type        = list(string)
  default     = []
}

variable "refs" {
  description = "Git refs allowed to assume the role, e.g. [\"refs/heads/main\"]."
  type        = list(string)
  default     = []
}

variable "create_oidc_provider" {
  description = "Create the account-wide OIDC provider. Set false when it already exists."
  type        = bool
  default     = false
}

variable "oidc_thumbprints" {
  description = "Thumbprints for the GitHub OIDC provider, used only when creating it."
  type        = list(string)
  default     = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

variable "state_bucket" {
  description = "Terraform state bucket this lane may read and write. Null grants no state access."
  type        = string
  default     = null
}

variable "state_key_prefix" {
  description = "State key prefix the lane may touch inside the bucket."
  type        = string
  default     = ""
}

variable "policy_arns" {
  description = "Managed policy ARNs to attach, keyed by a review-friendly name."
  type        = map(string)
  default     = {}
}

variable "inline_policy_json" {
  description = "Inline policy JSON documents to attach, keyed by policy name."
  type        = map(string)
  default     = {}
}

variable "max_session_duration" {
  description = "Maximum assumed-session duration in seconds."
  type        = number
  default     = 3600
}

variable "tags" {
  description = "Tags applied to the role and policies."
  type        = map(string)
  default     = {}
}
