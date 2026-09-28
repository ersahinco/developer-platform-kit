################################################################################
# __STACK_NAME__
#
# One Terraform root wiring the toolkit modules into one stack. This is a
# starting point: capabilities follow the workloads in stack.tfvars.
#
# Module sources are pinned to __TOOLKIT_REF__. Bump the ref deliberately, plan,
# read the diff, then apply.
################################################################################

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

locals {
  name           = var.stack_name
  has_data       = length(var.data_pipelines) > 0
  has_workloads  = length(var.services) > 0 || local.has_data
  has_public     = anytrue([for service in values(var.services) : service.public])
  needs_database = local.has_data || anytrue([for service in values(var.services) : service.needs_database])

  tags = {
    Project   = var.stack_name
    ManagedBy = "terraform"
    Repo      = "__REPOSITORY__"
  }
}

module "network" {
  count  = local.has_workloads ? 1 : 0
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/network?ref=__TOOLKIT_REF__"

  name               = local.name
  region             = var.aws_region
  vpc_cidr           = var.vpc_cidr
  availability_zones = data.aws_availability_zones.available.names
  single_nat_gateway = var.single_nat_gateway

  tags = local.tags
}

module "ecr" {
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/ecr?ref=__TOOLKIT_REF__"

  for_each = toset(concat(
    keys(var.services),
    [for name in keys(var.data_pipelines) : "${name}-migrations"],
  ))
  name = each.key

  tags = local.tags
}

module "cluster" {
  count  = local.has_workloads ? 1 : 0
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/ecs-cluster?ref=__TOOLKIT_REF__"

  name = local.name

  tags = local.tags
}

module "edge" {
  count  = local.has_public ? 1 : 0
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/alb?ref=__TOOLKIT_REF__"

  name            = local.name
  vpc_id          = module.network[0].vpc_id
  vpc_cidr        = module.network[0].vpc_cidr
  subnet_ids      = module.network[0].public_subnet_ids
  certificate_arn = var.certificate_arn
  target_port     = var.edge_target_port

  # No certificate yet means plaintext on a public listener. Acknowledge it
  # explicitly rather than discovering it in a scan later.
  allow_public_http = var.allow_public_http

  tags = local.tags
}

module "database" {
  count  = local.needs_database ? 1 : 0
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/postgres?ref=__TOOLKIT_REF__"

  name          = local.name
  vpc_id        = module.network[0].vpc_id
  subnet_ids    = module.network[0].intra_subnet_ids
  database_name = var.database_name
  multi_az      = var.database_multi_az

  tags = local.tags
}

module "artifacts" {
  count  = local.has_data ? 1 : 0
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/object-storage?ref=__TOOLKIT_REF__"

  name = "${local.name}-artifacts-${data.aws_caller_identity.current.account_id}"

  tags = local.tags
}

module "services" {
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/ecs-service?ref=__TOOLKIT_REF__"

  for_each = var.services

  name       = each.key
  cluster_id = module.cluster[0].cluster_id

  # Terraform creates the service with a placeholder. The deploy lane owns which
  # image actually runs, so this value is never updated in place.
  image          = "${module.ecr[each.key].repository_url}:bootstrap"
  container_name = "app"
  container_port = each.value.container_port
  cpu            = each.value.cpu
  memory         = each.value.memory
  desired_count  = each.value.desired_count

  vpc_id     = module.network[0].vpc_id
  subnet_ids = module.network[0].private_subnet_ids

  load_balancer_security_group_id = each.value.public ? module.edge[0].security_group_id : null
  target_group_arn                = each.value.public ? module.edge[0].default_target_group_arn : null
  extra_security_group_ids        = each.value.needs_database ? [module.database[0].client_security_group_id] : []

  environment = merge(
    {
      WORKLOAD_NAME = each.key
      ENVIRONMENT   = var.environment
      LOG_LEVEL     = var.log_level
    },
    each.value.needs_database ? { DATABASE_HOST = module.database[0].address } : {},
    each.value.environment,
  )

  secrets = merge(
    each.value.needs_database ? { DATABASE_SECRET = module.database[0].master_secret_arn } : {},
    each.value.secrets,
  )

  # A container health check is deliberately not set here: it would assume which
  # tools exist inside someone else's image. The load balancer already polls
  # /health, and a workload that wants a container-level check adds it knowing
  # what its image contains.

  tags = merge(local.tags, { Workload = each.key })
}

################################################################################
# Data
#
# One migration task family per pipeline, and one shared Spark application.
################################################################################

module "migrations" {
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/ecs-job?ref=__TOOLKIT_REF__"

  for_each = var.data_pipelines

  name           = "${each.key}-migrations"
  image          = "${module.ecr["${each.key}-migrations"].repository_url}:bootstrap"
  container_name = "liquibase"

  vpc_id = module.network[0].vpc_id

  # Liquibase reads the connection from the environment. The credential itself is
  # injected from the RDS-managed secret, so no password exists in this repo.
  environment = {
    LIQUIBASE_COMMAND_URL = "jdbc:postgresql://${module.database[0].endpoint}/${var.database_name}"
  }

  secrets = {
    LIQUIBASE_COMMAND_USERNAME = "${module.database[0].master_secret_arn}:username::"
    LIQUIBASE_COMMAND_PASSWORD = "${module.database[0].master_secret_arn}:password::"
  }

  tags = merge(local.tags, { Pipeline = each.key })
}

module "spark" {
  count  = local.has_data ? 1 : 0
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/emr-serverless?ref=__TOOLKIT_REF__"

  name = "${local.name}-spark"

  # Jobs here read and write S3 and the Glue catalog, so they need no VPC
  # placement. Give them subnet_ids only when a job must reach the database, and
  # accept the NAT cost that comes with it.
  data_bucket_names = [module.artifacts[0].bucket_name]

  tags = local.tags
}

module "delivery_identity" {
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/github-oidc?ref=__TOOLKIT_REF__"

  name              = "${local.name}-infra-delivery"
  github_repository = "__REPOSITORY__"
  environments      = ["aws"]
  refs              = ["refs/heads/main"]
  state_bucket      = var.state_bucket
  state_key_prefix  = "${var.stack_name}/"

  # This role applies this stack. Grant it the services this root
  # actually manages, and review changes to this list like any other permission
  # change.
  policy_arns = var.delivery_policy_arns

  tags = local.tags
}
