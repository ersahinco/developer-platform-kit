output "cluster_id" {
  description = "Cluster ARN."
  value       = aws_ecs_cluster.this.id
}

output "cluster_name" {
  description = "Cluster name, used by the deploy lane."
  value       = aws_ecs_cluster.this.name
}

output "service_discovery_namespace_id" {
  description = "Private DNS namespace ID, or null when service discovery is off."
  value       = try(aws_service_discovery_private_dns_namespace.this[0].id, null)
}
