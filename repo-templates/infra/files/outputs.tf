################################################################################
# Outputs
#
# These are the values workload repos need as GitHub variables and secrets. They
# are read from here, not copied into a second config file.
################################################################################

output "ecs_cluster" {
  description = "Set as the ECS_CLUSTER variable in every workload repo."
  value       = module.cluster.cluster_name
}

output "private_subnet_ids" {
  description = "Set as the PRIVATE_SUBNET_IDS variable for job repos, comma separated."
  value       = join(",", module.network.private_subnet_ids)
}

output "migration_security_group_ids" {
  description = <<-EOT
    Per pipeline, set as MIGRATION_SECURITY_GROUP_IDS in that data repo. Both
    groups are needed: the job group for image pull and secret fetch, the client
    group for the database itself.
  EOT
  value = {
    for name, job in module.migrations :
    name => join(",", [job.security_group_id, module.database.client_security_group_id])
  }
}

output "emr_application_id" {
  description = "Set as EMR_APPLICATION_ID in data repos."
  value       = module.spark.application_id
}

output "emr_job_role_arn" {
  description = "Set as EMR_JOB_ROLE_ARN in data repos."
  value       = module.spark.job_role_arn
}

output "data_code_bucket" {
  description = "Set as DATA_CODE_BUCKET in data repos. Holds job code, reports, and curated output."
  value       = module.artifacts.bucket_name
}

output "delivery_role_arn" {
  description = "Set as the AWS_ROLE_ARN secret on this repo's aws environment."
  value       = module.delivery_identity.role_arn
}

output "ecr_repository_urls" {
  description = "Image repository per workload."
  value       = { for name, repository in module.ecr : name => repository.repository_url }
}

output "edge_dns_name" {
  description = "Public entry point for the stack."
  value       = module.edge.dns_name
}

output "database_secret_arn" {
  description = "RDS-managed credential secret. Inject it; never copy the value."
  value       = module.database.master_secret_arn
}

output "service_log_groups" {
  description = "Log group per workload, for incident response."
  value       = { for name, service in module.services : name => service.log_group_name }
}
