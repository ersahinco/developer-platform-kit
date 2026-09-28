################################################################################
# ECS cluster
#
# Fargate only. Container Insights on by default because the first question in
# an incident is always what the task was doing.
################################################################################

resource "aws_ecs_cluster" "this" {
  name = var.name

  setting {
    name  = "containerInsights"
    value = var.container_insights ? "enhanced" : "disabled"
  }

  tags = var.tags
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = var.capacity_providers

  default_capacity_provider_strategy {
    capacity_provider = var.default_capacity_provider
    weight            = 100
    base              = 0
  }
}
