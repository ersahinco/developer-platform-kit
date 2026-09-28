output "cluster_id" {
  description = "Cluster ARN."
  value       = aws_ecs_cluster.this.id
}

output "cluster_name" {
  description = "Cluster name, used by the deploy lane."
  value       = aws_ecs_cluster.this.name
}
