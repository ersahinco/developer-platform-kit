################################################################################
# ECR repositories
#
# All workload/support image repositories share the same baseline: immutable tags,
# scan-on-push, GitHub Actions write access, and short untagged retention.
################################################################################

locals {
  ecr_repositories = {
    app = {
      repository_name = "app"
      tag_prefixes    = ["sha-"]
      keep_count      = 10
    }
    worker = {
      repository_name = "worker"
      tag_prefixes    = ["sha-"]
      keep_count      = 10
    }
    liquibase = {
      repository_name = "liquibase"
      tag_prefixes    = ["sha-"]
      keep_count      = 10
    }
    data_export_job = {
      repository_name = "data-export-job"
      tag_prefixes    = ["sha-"]
      keep_count      = 10
    }
    order_event_consumer = {
      repository_name = "order-event-consumer"
      tag_prefixes    = ["sha-"]
      keep_count      = 10
    }
    pgbouncer = {
      repository_name = "pgbouncer"
      tag_prefixes    = ["v"]
      keep_count      = 5
    }
  }
}

module "ecr" {
  for_each = local.ecr_repositories

  source  = "terraform-aws-modules/ecr/aws"
  version = "~> 3.0"

  repository_name                 = "${local.name}/${each.value.repository_name}"
  repository_image_tag_mutability = "IMMUTABLE"
  repository_image_scan_on_push   = true

  repository_read_write_access_arns = [local.github_actions_role_arn]

  repository_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep last ${each.value.keep_count} tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = each.value.tag_prefixes
          countType     = "imageCountMoreThan"
          countNumber   = each.value.keep_count
        }
        action = { type = "expire" }
      }
    ]
  })

  tags = local.tags
}

moved {
  from = module.ecr_app
  to   = module.ecr["app"]
}

moved {
  from = module.ecr_worker
  to   = module.ecr["worker"]
}

moved {
  from = module.ecr_liquibase
  to   = module.ecr["liquibase"]
}

moved {
  from = module.ecr_data_export_job
  to   = module.ecr["data_export_job"]
}

moved {
  from = module.ecr_order_event_consumer
  to   = module.ecr["order_event_consumer"]
}

moved {
  from = module.ecr_pgbouncer
  to   = module.ecr["pgbouncer"]
}
