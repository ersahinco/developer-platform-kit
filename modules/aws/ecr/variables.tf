variable "name" {
  description = "Immutable container image repository name."
  type        = string
}

variable "keep_image_count" {
  description = "How many tagged images to retain per repository."
  type        = number
  default     = 30
  validation {
    condition     = var.keep_image_count >= 1 && floor(var.keep_image_count) == var.keep_image_count
    error_message = "Keep at least one image."
  }
}

variable "untagged_expiry_days" {
  description = "Days before an untagged image expires."
  type        = number
  default     = 7
  validation {
    condition     = var.untagged_expiry_days >= 1 && floor(var.untagged_expiry_days) == var.untagged_expiry_days
    error_message = "Untagged expiry must be a positive whole number of days."
  }
}

variable "kms_key_arn" {
  description = "Customer-managed key for image encryption. Null uses AES256."
  type        = string
  default     = null
}

variable "force_delete" {
  description = "Allow Terraform to delete a repository that still holds images."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags applied to every repository."
  type        = map(string)
  default     = {}
}
