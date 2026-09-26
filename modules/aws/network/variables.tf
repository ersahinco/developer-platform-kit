variable "name" {
  description = "Name prefix for every network resource."
  type        = string
}

variable "region" {
  description = "AWS region, used to build endpoint service names."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC. Needs room for /20 private subnets."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones to choose from, in order."
  type        = list(string)
}

variable "az_count" {
  description = "How many availability zones to use."
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 6 && floor(var.az_count) == var.az_count && length(var.availability_zones) >= var.az_count
    error_message = "az_count must be an integer from 2 to 6 and availability_zones must contain that many zones."
  }
}

variable "single_nat_gateway" {
  description = "Use one shared NAT gateway. Cheaper, and a single AZ failure removes egress."
  type        = bool
  default     = true
}

variable "enable_ssm_exec_endpoints" {
  description = "Add the ssmmessages endpoint so ECS Exec works on private tasks."
  type        = bool
  default     = true
}

variable "extra_interface_endpoints" {
  description = "Additional interface endpoint short names, e.g. [\"sqs\", \"sns\"]."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
