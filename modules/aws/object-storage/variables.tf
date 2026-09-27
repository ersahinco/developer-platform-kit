variable "name" {
  description = "Globally unique bucket name. Include the account ID or stack name."
  type        = string
}

variable "versioning_enabled" {
  description = "Keep previous object versions."
  type        = bool
  default     = true
}

variable "kms_key_arn" {
  description = "Customer-managed key for object encryption. Null uses AES256."
  type        = string
  default     = null
}

variable "expire_current_after_days" {
  description = "Expire current objects after this many days. Null keeps them."
  type        = number
  default     = null
}

variable "expire_prefix" {
  description = "Prefix the expiry rule applies to. Empty means the whole bucket."
  type        = string
  default     = ""
}

variable "noncurrent_expiry_days" {
  description = "Days before a noncurrent version expires."
  type        = number
  default     = 30
  validation {
    condition     = var.noncurrent_expiry_days >= 1 && floor(var.noncurrent_expiry_days) == var.noncurrent_expiry_days
    error_message = "Keep noncurrent versions for at least one whole day."
  }
}

variable "force_destroy" {
  description = "Allow Terraform to delete a bucket that still holds objects."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags applied to the bucket."
  type        = map(string)
  default     = {}
}
