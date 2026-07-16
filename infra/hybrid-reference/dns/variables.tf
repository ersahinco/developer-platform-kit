variable "cloudflare_zone_id" {
  description = "Existing Cloudflare zone ID."
  type        = string
}

variable "hostname" {
  description = "Fully qualified workload hostname."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$", var.hostname))
    error_message = "hostname must be a lowercase fully qualified DNS name."
  }
}

variable "origin_ipv4" {
  description = "Verified Hetzner origin IPv4 address."
  type        = string

  validation {
    condition     = can(cidrhost("${var.origin_ipv4}/32", 0))
    error_message = "origin_ipv4 must be a valid IPv4 address."
  }
}

variable "ttl" {
  description = "DNS record TTL in seconds."
  type        = number
  default     = 60

  validation {
    condition     = var.ttl >= 60
    error_message = "ttl must be at least 60 seconds."
  }
}
