################################################################################
# __STACK_NAME__
#
# One Terraform root wiring the toolkit modules into one stack. This is a
# starting point, not a framework: delete the blocks this stack does not need
# and change the ones it keeps. Nothing here reads a hidden config file.
#
# Module sources are pinned to __TOOLKIT_REF__. Bump the ref deliberately, plan,
# read the diff, then apply.
################################################################################

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

locals {
  name = var.stack_name

  tags = {
    Project   = var.stack_name
    ManagedBy = "terraform"
    Repo      = "__GITHUB_REPOSITORY__"
  }
}

module "network" {
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
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/ecs-cluster?ref=__TOOLKIT_REF__"

  name   = local.name
  vpc_id = module.network.vpc_id

  tags = local.tags
}

module "edge" {
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/alb?ref=__TOOLKIT_REF__"

  name            = local.name
  vpc_id          = module.network.vpc_id
  vpc_cidr        = module.network.vpc_cidr
  subnet_ids      = module.network.public_subnet_ids
  certificate_arn = var.certificate_arn
  target_port     = var.edge_target_port

  # No certificate yet means plaintext on a public listener. Acknowledge it
  # explicitly rather than discovering it in a scan later.
  allow_public_http = var.allow_public_http

  tags = local.tags
}

# Delete this block if the stack has no relational database. The services block
# below references it through needs_database, so remove those two lines too.
module "database" {
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/postgres?ref=__TOOLKIT_REF__"

  name          = local.name
  vpc_id        = module.network.vpc_id
  subnet_ids    = module.network.intra_subnet_ids
  database_name = var.database_name
  multi_az      = var.database_multi_az

  tags = local.tags
}

# Delete this block if no workload needs object storage.
module "artifacts" {
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/object-storage?ref=__TOOLKIT_REF__"

  name = "${local.name}-artifacts-${data.aws_caller_identity.current.account_id}"

  tags = local.tags
}

module "services" {
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/ecs-service?ref=__TOOLKIT_REF__"

  for_each = var.services

  name         = each.key
  cluster_id   = module.cluster.cluster_id
  cluster_name = module.cluster.cluster_name

  # Terraform creates the service with a placeholder. The deploy lane owns which
  # image actually runs, so this value is never updated in place.
  image          = "${module.ecr[each.key].repository_url}:bootstrap"
  container_name = "app"
  container_port = each.value.container_port
  cpu            = each.value.cpu
  memory         = each.value.memory
  desired_count  = each.value.desired_count

  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnet_ids

  load_balancer_security_group_id = each.value.public ? module.edge.security_group_id : null
  target_group_arn                = each.value.public ? module.edge.default_target_group_arn : null
  extra_security_group_ids        = each.value.needs_database ? [module.database.client_security_group_id] : []

  environment = merge(
    {
      WORKLOAD_NAME = each.key
      ENVIRONMENT   = var.environment
      LOG_LEVEL     = var.log_level
    },
    each.value.needs_database ? { DATABASE_HOST = module.database.address } : {},
    each.value.environment,
  )

  secrets = merge(
    each.value.needs_database ? { DATABASE_SECRET = module.database.master_secret_arn } : {},
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
# Delete both blocks and the data_pipelines variable if this stack has no data
# work.
################################################################################

module "migrations" {
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/ecs-job?ref=__TOOLKIT_REF__"

  for_each = var.data_pipelines

  name           = "${each.key}-migrations"
  cluster_id     = module.cluster.cluster_id
  image          = "${module.ecr["${each.key}-migrations"].repository_url}:bootstrap"
  container_name = "liquibase"

  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnet_ids

  # Liquibase reads the connection from the environment. The credential itself is
  # injected from the RDS-managed secret, so no password exists in this repo.
  environment = {
    LIQUIBASE_COMMAND_URL = "jdbc:postgresql://${module.database.endpoint}/${var.database_name}"
  }

  secrets = {
    LIQUIBASE_COMMAND_USERNAME = "${module.database.master_secret_arn}:username::"
    LIQUIBASE_COMMAND_PASSWORD = "${module.database.master_secret_arn}:password::"
  }

  tags = merge(local.tags, { Pipeline = each.key })
}

module "spark" {
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/emr-serverless?ref=__TOOLKIT_REF__"

  name = "${local.name}-spark"

  # Jobs here read and write S3 and the Glue catalog, so they need no VPC
  # placement. Give them subnet_ids only when a job must reach the database, and
  # accept the NAT cost that comes with it.
  data_bucket_names = [module.artifacts.bucket_name]

  tags = local.tags
}

module "delivery_identity" {
  source = "git::https://github.com/__TOOLKIT_REPOSITORY__.git//modules/aws/github-oidc?ref=__TOOLKIT_REF__"

  name              = "${local.name}-infra-delivery"
  github_repository = "__GITHUB_REPOSITORY__"
  environments      = ["aws"]
  refs              = ["refs/heads/main"]
  state_bucket      = var.state_bucket
  state_key_prefix  = "${var.stack_name}/"

  # This role plans and applies this stack. Grant it the services this root
  # actually manages, and review changes to this list like any other permission
  # change.
  policy_arns = var.delivery_policy_arns

  tags = local.tags
}
