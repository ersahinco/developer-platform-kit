variable "name" {
  description = "Cluster name."
  type        = string
}

variable "vpc_id" {
  description = "VPC that hosts the optional service discovery namespace."
  type        = string
  default     = null
}

variable "container_insights" {
  description = "Enable enhanced Container Insights."
  type        = bool
  default     = true
}

variable "capacity_providers" {
  description = "Capacity providers available to the cluster."
  type        = list(string)
  default     = ["FARGATE", "FARGATE_SPOT"]
}

variable "default_capacity_provider" {
  description = "Capacity provider used when a service names none."
  type        = string
  default     = "FARGATE"
}

variable "service_discovery_namespace" {
  description = "Private DNS namespace for service-to-service calls, e.g. \"internal\". Null skips it."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
