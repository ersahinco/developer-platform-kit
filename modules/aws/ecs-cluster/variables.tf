variable "name" {
  description = "Cluster name."
  type        = string
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

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
