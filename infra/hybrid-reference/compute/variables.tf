variable "stack_name" {
  description = "Stable stack prefix for starter compute resources."
  type        = string
  default     = "aws-sdlc-containers"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{2,39}$", var.stack_name))
    error_message = "stack_name must be 3-40 lowercase letters, digits, or hyphens."
  }
}

variable "server_type" {
  description = "Hetzner server type for the single-VM starter target."
  type        = string
  default     = "cx33"
}

variable "server_location" {
  description = "Hetzner server location."
  type        = string
  default     = "nbg1"
}

variable "server_image" {
  description = "Hetzner server image."
  type        = string
  default     = "ubuntu-24.04"
}

variable "ssh_public_key" {
  description = "Public SSH key installed for the platform operator."
  type        = string

  validation {
    condition     = can(regex("^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp256) ", var.ssh_public_key))
    error_message = "ssh_public_key must be an OpenSSH public key."
  }
}

variable "admin_cidrs" {
  description = "IPv4 or IPv6 CIDRs allowed to connect over SSH."
  type        = list(string)

  validation {
    condition = length(var.admin_cidrs) > 0 && alltrue([
      for cidr in var.admin_cidrs :
      can(cidrhost(cidr, 0)) && !contains(["0.0.0.0/0", "::/0"], cidr)
    ])
    error_message = "admin_cidrs must contain valid restricted CIDRs; unrestricted SSH is rejected."
  }
}
