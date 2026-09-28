# Exercise the rendered composition without AWS credentials or resources.
mock_provider "aws" {}

override_module {
  target = module.network
  outputs = {
    vpc_id             = "vpc-test"
    vpc_cidr           = "10.0.0.0/16"
    public_subnet_ids  = ["subnet-public"]
    private_subnet_ids = ["subnet-private"]
    intra_subnet_ids   = ["subnet-database"]
  }
}
override_module {
  target  = module.cluster
  outputs = { cluster_id = "cluster-test", cluster_name = "test" }
}
override_module {
  target = module.edge
  outputs = {
    security_group_id        = "sg-edge"
    default_target_group_arn = "target-test"
    dns_name                 = "test.example.com"
  }
}
override_module {
  target = module.database
  outputs = {
    client_security_group_id = "sg-database-client"
    address                  = "database.example.com"
    endpoint                 = "database.example.com:5432"
    master_secret_arn        = "arn:aws:secretsmanager:eu-central-1:123456789012:secret:database"
  }
}
override_module {
  target  = module.artifacts
  outputs = { bucket_name = "test-artifacts" }
}
override_module {
  target  = module.spark
  outputs = { application_id = "spark-test", job_role_arn = "role-test" }
}
override_module {
  target  = module.ecr
  outputs = { repository_url = "registry.example.com/test" }
}
override_module {
  target  = module.services
  outputs = { log_group_name = "/ecs/test" }
}
override_module {
  target  = module.migrations
  outputs = { security_group_id = "sg-migration" }
}
override_module {
  target  = module.delivery_identity
  outputs = { role_arn = "role-test" }
}

run "empty" {
  command = plan
  assert {
    condition = alltrue([
      length(module.network) == 0, length(module.cluster) == 0,
      length(module.edge) == 0, length(module.database) == 0,
      length(module.artifacts) == 0, length(module.spark) == 0,
      length(module.ecr) == 0, length(module.services) == 0,
      length(module.migrations) == 0,
      output.ecs_cluster == null, output.private_subnet_ids == null,
      output.edge_dns_name == null, output.database_secret_arn == null,
      output.data_code_bucket == null, output.emr_application_id == null,
      output.emr_job_role_arn == null,
    ])
    error_message = "Empty workload maps must not create workload infrastructure or expose absent outputs."
  }
}

run "private_service" {
  command = plan
  variables {
    services = { api = {} }
  }
  assert {
    condition = alltrue([
      length(module.network) == 1, length(module.cluster) == 1,
      length(module.ecr) == 1, length(module.services) == 1,
      length(module.edge) == 0, length(module.database) == 0,
      length(module.artifacts) == 0, length(module.spark) == 0,
    ])
    error_message = "A private stateless service needs only network, cluster, ECR, and service."
  }
}

run "public_service" {
  command = plan
  variables {
    services = { api = { public = true } }
  }
  assert {
    condition     = length(module.edge) == 1 && length(module.database) == 0 && length(module.spark) == 0
    error_message = "A public service adds an ALB, not a database or data platform."
  }
}

run "database_service" {
  command = plan
  variables {
    services = { api = { needs_database = true } }
  }
  assert {
    condition     = length(module.database) == 1 && length(module.edge) == 0 && length(module.artifacts) == 0
    error_message = "A private database consumer adds PostgreSQL without an ALB or data bucket."
  }
}

run "pipeline" {
  command = plan
  variables {
    data_pipelines = { daily = {} }
  }
  assert {
    condition = alltrue([
      length(module.network) == 1, length(module.cluster) == 1,
      length(module.database) == 1, length(module.migrations) == 1,
      length(module.ecr) == 1, length(module.artifacts) == 1,
      length(module.spark) == 1, length(module.edge) == 0,
      length(module.services) == 0,
    ])
    error_message = "A pipeline needs migration and Spark infrastructure, without an ALB or app service."
  }
}
